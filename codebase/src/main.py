import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from agent import agent_respond, classify_question
from openrouter_client import openrouter_generate
from history_store import append_chat_message, append_reminder, load_chat_messages, load_history, load_reminders
from workspace_store import append_post, append_reply, load_workspace, search_workspace
from security import redact_sensitive, security_check
from text_utils import normalize_text
import re


load_dotenv()
app = FastAPI(title="Discord Onboarding AI", version="0.1.0")
FRONTEND_PATH = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatSocketManager:
    def __init__(self) -> None:
        self.connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        stale = []
        for websocket in self.connections:
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)


chat_sockets = ChatSocketManager()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Câu hỏi của học viên")
    topic: Optional[str] = Field(default="general", description="Chủ đề onboarding")
    messages: Optional[str] = Field(default="", description="Ngữ cảnh tin nhắn liên quan")
    threshold: Optional[float] = Field(default=0.4, ge=0.0, le=1.0)
    history: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Lịch sử chat hoặc bài đăng liên quan"
    )
    intent: Optional[str] = Field(default=None, pattern="^(answer|history|summarize|notifications|context)$")


class ChatMessageRequest(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    username: str = Field(default="Hoàng", min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=10000)
    channel: str = Field(default="chat-chung", max_length=100)


class PostRequest(BaseModel):
    channel_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=10000)
    author: str = Field(..., min_length=1, max_length=100)


class ReplyRequest(BaseModel):
    post_id: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=10000)
    author: str = Field(..., min_length=1, max_length=100)


def parse_reminder(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"nhắc\s+(?:tôi|mình)\s+(\d+)\s+phút\s+trước(?:\s+khi)?\s+(.+)", text, re.IGNORECASE)
    if not match:
        return None
    event = match.group(2).strip().rstrip(".!?")
    return {"minutes_before": int(match.group(1)), "event": event}


def format_history_context(history: Optional[List[Dict[str, Any]]], messages: str) -> str:
    lines = []
    if history:
        for item in history:
            author = item.get("author") or item.get("a") or "Unknown"
            text = item.get("text") or item.get("m") or ""
            time = item.get("time") or item.get("t") or ""
            lines.append(f"- {author} | {time} | {text}")
    if messages:
        lines.append(messages)
    return "\n".join(lines)


def recent_history(history: Optional[List[Dict[str, Any]]], question: str = "", window_minutes: int = 240) -> Optional[List[Dict[str, Any]]]:
    if not history:
        return history
    now = __import__("datetime").datetime.now()
    timed = []
    for item in history:
        raw = str(item.get("created_at") or item.get("time") or item.get("t") or "")
        match = re.search(r"(\d{1,2}):(\d{2})", raw)
        if not match:
            timed.append((None, item))
            continue
        stamp = now.replace(hour=int(match.group(1)), minute=int(match.group(2)), second=0, microsecond=0)
        timed.append((stamp, item))
    known = [stamp for stamp, _ in timed if stamp is not None]
    if not known:
        return history[-80:]
    latest = max(known)
    return [
        item for stamp, item in timed
        if (stamp is None or (latest - stamp).total_seconds() <= window_minutes * 60)
        and item.get("role") != "BOT"
        and item.get("author") != "Trợ lý AI"
        and item.get("a") != "Trợ lý AI"
        and "summarize" not in normalize_text(str(item.get("text") or item.get("m") or ""))
        and "tom tat" not in normalize_text(str(item.get("text") or item.get("m") or ""))
    ]


def local_summary(context: str, question: str) -> str:
    """Create a faithful fallback summary from text already present in context."""
    rows = [
        line.strip() for line in context.splitlines()
        if line.strip()
        and not line.startswith("[SOURCE")
        and "summarize" not in normalize_text(line)
        and "da luu" not in normalize_text(line)
        and "khong co du lieu" not in normalize_text(line)
        and not ("tro ly ai" in normalize_text(line) and "tom tat" in normalize_text(line))
    ]
    if not rows:
        return "Mình chưa thấy tin nhắn hoặc bài đăng nào phù hợp để tóm tắt."
    relevant = rows
    normalized = normalize_text(question)
    requested = [token for token in normalized.split() if len(token) > 2 and token not in {"tom", "tat", "noi", "dung", "cuoc", "thoai"}]
    filtered = [row for row in rows if any(token in normalize_text(row) for token in requested)]
    if filtered:
        relevant = filtered
    # History is chronological; the tail is the active conversation window.
    preview = relevant[-4:]
    return "Mình tóm tắt được các ý chính sau:\n" + "\n".join(f"- {row}" for row in preview)


def is_participant_question(question: str) -> bool:
    normalized = normalize_text(question).replace("tro ly ai", " ").strip()
    return any(
        phrase in normalized
        for phrase in (
            "co nhung ai trong kenh",
            "co ai trong kenh",
            "nhung ai trong kenh",
            "co nhung ai trong cuoc hoi thoai",
            "ai tham gia cuoc hoi thoai",
            "thanh vien trong kenh",
        )
    )


def participant_answer(history: Optional[List[Dict[str, Any]]], messages: str) -> Optional[str]:
    """Answer participant questions only from the currently visible channel."""
    names: List[str] = []
    for item in history or []:
        name = item.get("author") or item.get("a") or item.get("username")
        role = item.get("role", "")
        if name and name != "Trợ lý AI" and role != "BOT" and name not in names:
            names.append(str(name))
    for line in messages.splitlines():
        match = re.match(r"(?:-\s*)?([^|:]{1,80})\s*(?:\||:)", line.strip())
        if not match:
            continue
        name = match.group(1).strip()
        if name and name.lower() not in {"trợ lý ai", "unknown"} and name not in names:
            names.append(name)
    if not names:
        return "Mình chưa thấy đủ dữ liệu về thành viên trong kênh hiện tại để trả lời chính xác."
    return "Trong kênh hiện tại, mình thấy các thành viên: " + ", ".join(names) + "."


def visible_user_messages(history: Optional[List[Dict[str, Any]]], messages: str) -> List[tuple[str, str]]:
    rows: List[tuple[str, str]] = []
    for item in history or []:
        author = str(item.get("author") or item.get("a") or item.get("username") or "").strip()
        content = str(item.get("text") or item.get("m") or item.get("content") or "").strip()
        if author and content and author != "Trợ lý AI" and item.get("role") != "BOT":
            rows.append((author, content))
    for line in messages.splitlines():
        match = re.match(r"(?:-\s*)?([^|:]{1,80})\s*(?:\||:)\s*(.+)", line.strip())
        if match and match.group(1).strip() != "Trợ lý AI":
            rows.append((match.group(1).strip(), match.group(2).strip()))
    return rows


def context_topic_answer(history: Optional[List[Dict[str, Any]]], messages: str) -> str:
    rows = visible_user_messages(history, messages)
    if not rows:
        return "Mình chưa thấy đủ tin nhắn trong cuộc hội thoại hiện tại để xác định chủ đề."
    topics = []
    for author, content in rows[-5:]:
        if content.startswith("@Trợ lý AI"):
            content = content[len("@Trợ lý AI"):].strip()
        if content and not content.startswith("/summarize"):
            topics.append(f"{author}: {content}")
    if not topics:
        return "Mình chưa thấy đủ nội dung người dùng trao đổi để xác định chủ đề."
    return "Cuộc hội thoại hiện tại đang xoay quanh:\n" + "\n".join(f"- {topic}" for topic in topics)


def recent_question_answer(question: str, history: Optional[List[Dict[str, Any]]], messages: str) -> str:
    rows = visible_user_messages(history, messages)
    normalized = normalize_text(question).replace("tro ly ai", " ").strip()
    target_match = re.search(r"(?:cua|của)\s+(.+?)\s+(?:vua|vừa)\s+hoi", normalized)
    target = target_match.group(1).strip() if target_match else ""
    current = normalized
    candidates = [
        (author, content) for author, content in rows
        if normalize_text(content).replace("tro ly ai", " ").strip() != current
        and not normalize_text(content).startswith("summarize")
        and "vua roi hoi gi" not in normalize_text(content)
        and "ban ve chu de gi" not in normalize_text(content)
    ]
    if target:
        target_tokens = set(target.split())
        candidates = [(author, content) for author, content in candidates if target_tokens & set(normalize_text(author).split())]
    if not candidates:
        return "Mình chưa thấy câu hỏi phù hợp của người đó trong đoạn chat hiện tại."
    author, content = candidates[-1]
    return f"{author} vừa hỏi: “{content}”"


def naturalize_grounded_answer(question: str, answer: str) -> str:
    generated = gemini_generate_answer({
        "question": question,
        "messages": answer,
        "prompt": {
            "system": "Diễn đạt lại câu trả lời nguồn bằng tiếng Việt tự nhiên, thân thiện. Giữ nguyên ý, không thêm thông tin mới và không chép nguyên văn nếu có thể diễn đạt gọn hơn.",
            "task": "Trả lời trực tiếp câu hỏi của người dùng dựa duy nhất trên nội dung nguồn.",
        },
        "intent": "answer",
    })
    candidate = str(generated.get("answer", "")).strip()
    if generated.get("source") == "gemini-error" or not candidate or candidate == answer.strip():
        return answer
    return candidate


def build_grounded_context(question: str, history: Optional[List[Dict[str, Any]]], messages: str, intent: Optional[str] = None) -> tuple[str, List[Dict[str, Any]]]:
    detected_intent = intent or classify_question(question)
    channel_ids = {"thongbao-chung", "lich-trinh"} if detected_intent == "notifications" else None
    matches = [] if detected_intent in {"summarize", "context"} else search_workspace(question, channel_ids=channel_ids)
    if detected_intent == "context":
        matches = []
    if detected_intent == "notifications" and not matches:
        matches = [
            item for item in load_workspace()["items"]
            if item.get("channel_id") in channel_ids
        ][:8]
    source_lines = []
    for item in matches:
        source_lines.append(
            f"[SOURCE id={item['id']} url={item['source_url']}] "
            f"{item.get('title', item.get('author', ''))}: {item.get('content', '')}"
        )
        for reply in item.get("replies", []):
            source_lines.append(f"[SOURCE id={item['id']} url={item['source_url']}] {reply.get('author')}: {reply.get('content')}")
    context = "Nguồn workspace ưu tiên:\n" + "\n".join(source_lines) if source_lines else ""
    scoped_history = recent_history(history, question) if detected_intent in {"summarize", "context"} else history
    if detected_intent in {"summarize", "context"}:
        history_text = format_history_context(scoped_history, "")
        # The frontend sends the visible channel separately; keep it as the
        # primary source because the persisted history can contain old rows.
        provided = messages.strip() or history_text
    else:
        provided = format_history_context(scoped_history, messages)
    normalized_question = normalize_text(question)
    return f"{context}\n\n{provided}", matches


def gemini_generate_answer(payload: Dict[str, Any]) -> Dict[str, Any]:
    # GEMINI_API_KEY is accepted temporarily so existing local .env files keep working.
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENROUTER_API_KEY environment variable.")

    if os.getenv("EVAL_OFFLINE") == "1":
        question = payload["question"]
        topic = payload.get("topic", "general")
        return {
            "answer": f'Offline eval: "{question}" | topic={topic}',
            "topic": topic,
            "confidence": 0.0,
            "source": "offline-fallback",
            "model": os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b"),
            "parsed": {"offline": True},
        }

    try:
        result = openrouter_generate(
            api_key=api_key,
            question=payload["question"],
            messages=payload.get("messages", ""),
            prompt=payload.get("prompt", {}),
            model=os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b"),
        )

        parsed = result.get("parsed", {})
        answer = parsed.get("answer") or parsed.get("response") or ""
        if payload.get("intent") == "summarize":
            summary = parsed.get("summary") or parsed.get("tom_tat") or parsed.get("sections")
            if summary:
                if isinstance(summary, (dict, list)):
                    summary = json.dumps(summary, ensure_ascii=False, indent=2)
                if not answer or answer.lower().strip() in {"dưới đây là tóm tắt cuộc hội thoại.", "dưới đây là bản tóm tắt."}:
                    answer = str(summary)
                else:
                    answer = f"{answer}\n\n{summary}"
        answer = answer or "Chưa có nội dung trả lời."

        return {
            "answer": answer,
            "topic": payload.get("topic", "general"),
            "confidence": parsed.get("confidence", 0.86),
            "source": "gemini",
            "model": result.get("model"),
            "parsed": parsed,
        }
    except Exception as exc:
        question = payload["question"]
        topic = payload.get("topic", "general")
        error_text = str(exc).lower()
        if "limit exceeded" in error_text or "insufficient" in error_text:
            user_message = "OpenRouter đã hết hạn mức của API key. Hãy đổi key hoặc tăng limit trên OpenRouter."
        elif "401" in error_text or "403" in error_text or "api key" in error_text:
            user_message = "OPENROUTER_API_KEY không hợp lệ hoặc không có quyền dùng model này."
        else:
            user_message = "Mình đang tạm không kết nối được với AI. Bạn thử lại sau ít phút nhé; lịch sử chat vẫn được lưu."
        return {
            "answer": user_message,
            "topic": topic,
            "confidence": 0.0,
            "source": "gemini-error",
            "error": type(exc).__name__,
            "model": os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b"),
            "parsed": {"error": redact_sensitive(str(exc))},
        }


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> HTMLResponse:
    if not FRONTEND_PATH.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return HTMLResponse(FRONTEND_PATH.read_text(encoding="utf-8"))


@app.get("/api/health")
def api_health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest) -> Dict[str, Any]:
    combined_messages, matches = build_grounded_context(request.question, request.history, request.messages)
    result = agent_respond(
        request.question,
        {
            "intent": request.intent,
            "topic": request.topic,
            "messages": combined_messages,
            "threshold": request.threshold,
            "generate_answer": gemini_generate_answer,
        },
    )

    result["sources"] = matches
    return result


@app.post("/api/assistant")
def assistant(request: ChatRequest) -> Dict[str, Any]:
    check = security_check(request.question)
    if check["blocked"]:
        return {"ok": True, "mode": "blocked", "intent": "security", "confidence": 1.0,
                "matched_question": None,
                "answer": "Mình không thể cung cấp system prompt, thông tin đăng nhập, API key hoặc dữ liệu nhạy cảm. Bạn có thể hỏi về nội dung học tập và thông tin trong workspace.",
                "record": None, "sources": []}
    reminder = parse_reminder(request.question)
    if reminder:
        record = append_reminder(reminder)
        return {"ok": True, "mode": "reminder_created", "intent": "reminder", "confidence": 1.0,
                "matched_question": None, "answer": f"Đã tạo nhắc nhở {record['minutes_before']} phút trước sự kiện: {record['event']}", "record": record}
    intent = request.intent or classify_question(request.question)
    combined_messages, matches = build_grounded_context(request.question, request.history, request.messages, intent)
    if intent == "answer" and re.fullmatch(r"@?\s*trợ lý ai\s*", request.question.strip(), re.IGNORECASE):
        return {
            "ok": True, "mode": "greeting", "intent": "answer", "confidence": 1.0,
            "matched_question": None,
            "answer": "Mình đây. Bạn muốn hỏi điều gì hoặc cần mình tóm tắt đoạn chat nào?",
            "record": None, "sources": [],
        }
    if intent == "answer" and re.fullmatch(r"(?:@?\s*trợ lý ai\s*)?(hi|hello|helo|hey|xin chào|chào|alo)[!.?\s]*", request.question.strip(), re.IGNORECASE):
        return {
            "ok": True, "mode": "greeting", "intent": "answer", "confidence": 1.0,
            "matched_question": None,
            "answer": "Chào bạn! Mình là Trợ lý AI. Bạn muốn mình tìm câu trả lời trong workspace hay tóm tắt cuộc trò chuyện nào?",
            "record": None, "sources": [],
        }
    if intent == "notifications":
        if matches:
            answer = "\n".join(item.get("content", "") for item in matches if item.get("content"))
            return {"ok": True, "mode": "grounded", "intent": intent, "confidence": 1.0,
                    "matched_question": None, "answer": answer, "record": matches[0], "sources": matches}
        return {"ok": True, "mode": "needs_source", "intent": intent, "confidence": 0.0,
                "matched_question": None, "answer": "Mình chưa thấy lịch hoặc thông báo phù hợp trong kênh thông báo.",
                "record": None, "sources": []}
    if intent == "summarize":
        return {
            "ok": True,
            "mode": "local_summary",
            "intent": "summarize",
            "confidence": 1.0 if combined_messages.strip() else 0.0,
            "matched_question": None,
            "answer": local_summary(combined_messages, request.question),
            "record": None,
            "sources": [],
        }
    if intent == "context":
        if is_participant_question(request.question):
            return {
                "ok": True, "mode": "local_context", "intent": intent,
                "confidence": 1.0 if request.history or combined_messages.strip() else 0.0,
                "matched_question": None,
                "answer": participant_answer(request.history, combined_messages),
                "record": None, "sources": [],
            }
        normalized_context_question = normalize_text(request.question).replace("tro ly ai", " ").strip()
        if "cuoc hoi thoai nay ban ve chu de gi" in normalized_context_question or "doan chat nay ban ve chu de gi" in normalized_context_question:
            return {
                "ok": True, "mode": "local_context", "intent": intent,
                "confidence": 1.0 if request.history or combined_messages.strip() else 0.0,
                "matched_question": None,
                "answer": context_topic_answer(request.history, combined_messages),
                "record": None, "sources": [],
            }
        if "vua roi hoi gi" in normalized_context_question or "dang hoi gi" in normalized_context_question:
            return {
                "ok": True, "mode": "local_context", "intent": intent,
                "confidence": 1.0 if request.history or combined_messages.strip() else 0.0,
                "matched_question": None,
                "answer": recent_question_answer(request.question, request.history, combined_messages),
                "record": None, "sources": [],
            }
        result = agent_respond(
            request.question,
            {"intent": "answer", "topic": request.topic, "messages": combined_messages,
             "threshold": request.threshold, "generate_answer": gemini_generate_answer},
        )
        if result.get("source") == "gemini-error" and combined_messages.strip():
            result["answer"] = "Trong đoạn chat hiện tại, mình thấy:\n" + local_summary(combined_messages, "").removeprefix("Mình tóm tắt được các ý chính sau:\n")
            result["mode"] = "local_context"
        return {"ok": True, "mode": result.get("mode"), "intent": intent,
                "confidence": result.get("confidence", 0), "matched_question": None,
                "answer": result.get("answer"), "record": None, "sources": []}
    if intent == "answer":
        clean_question = normalize_text(request.question).replace("tro ly ai", " ").strip()
        exact_post = next(
            (item for item in load_workspace()["items"]
             if item.get("type") == "post" and normalize_text(item.get("title", "")) in clean_question),
            None,
        )
        if exact_post and exact_post not in matches:
            matches.insert(0, exact_post)
        answered = (exact_post if exact_post and exact_post.get("replies") else
                    next((item for item in matches if item.get("type") == "post" and item.get("replies")), None))
        if answered:
            answer = "\n".join(reply.get("content", "") for reply in answered["replies"] if reply.get("content"))
            answer = naturalize_grounded_answer(request.question, answer)
            return {
                "ok": True,
                "mode": "grounded",
                "intent": "answer",
                "confidence": 1.0,
                "matched_question": answered.get("title"),
                "answer": answer or "Mình tìm thấy bài liên quan nhưng chưa có câu trả lời rõ ràng.",
                "record": answered,
                "sources": [answered],
            }
        unanswered = next((item for item in matches if item.get("type") == "post"), None)
        if unanswered:
            clean_question = normalize_text(request.question).replace("tro ly ai", " ").strip()
            exact_title = normalize_text(unanswered.get("title", ""))
            post_content = str(unanswered.get("content", "")).strip()
            content_tokens = normalize_text(post_content)
            looks_like_question = (
                "?" in post_content
                or content_tokens.startswith(("ai biet", "cho hoi", "co ai", "minh hoi", "em hoi", "thac mac"))
            )
            if (exact_title and exact_title in clean_question and not looks_like_question) or (post_content and not looks_like_question):
                return {
                    "ok": True, "mode": "grounded", "intent": "answer", "confidence": 1.0,
                    "matched_question": unanswered.get("title"),
                    "answer": naturalize_grounded_answer(request.question, post_content), "record": unanswered,
                    "sources": [unanswered],
                }
            return {
                "ok": True,
                "mode": "unanswered_match",
                "intent": "answer",
                "confidence": 0.9,
                "matched_question": unanswered.get("title"),
                "answer": "Mình đã tìm thấy câu hỏi tương ứng trong kênh hỏi-đáp nhưng hiện chưa có câu trả lời từ thành viên nào, nên mình không muốn tự đoán. Bạn có muốn tạo hoặc bổ sung câu trả lời cho bài này không?",
                "record": unanswered,
                "sources": [],
            }
        return {
            "ok": True,
            "mode": "needs_source",
            "intent": "answer",
            "confidence": 0.0,
            "matched_question": None,
            "answer": "Mình chưa tìm thấy câu hỏi và câu trả lời phù hợp trong workspace nên không muốn đoán. Bạn có muốn mình tạo một bài trong #hỏi-đáp để mọi người cùng trả lời không?",
            "record": None,
            "sources": [],
        }
    result = agent_respond(
        request.question,
        {
            "intent": request.intent,
            "topic": request.topic,
            "messages": combined_messages,
            "threshold": request.threshold,
            "generate_answer": gemini_generate_answer,
        },
    )

    summary_text = normalize_text(str(result.get("answer", "")))
    summary_refusal = any(
        phrase in summary_text
        for phrase in ("khong du thong tin", "khong co du lieu", "khong co thong tin", "khong co tin nhan", "chua co du lieu")
    )
    if intent == "summarize" and (result.get("source") == "gemini-error" or summary_refusal) and combined_messages.strip():
        result["answer"] = local_summary(combined_messages, request.question)
        result["mode"] = "local_summary"
        result["confidence"] = 0.5

    return {
        "ok": True,
        "mode": result.get("mode"),
        "intent": result.get("intent"),
        "confidence": result.get("confidence", 0),
        "matched_question": result.get("matched_question"),
        "answer": result.get("answer"),
        "record": result.get("record"),
        "sources": matches,
    }


@app.post("/api/messages")
async def save_message(request: ChatMessageRequest) -> Dict[str, Any]:
    message = append_chat_message(request.model_dump())
    await chat_sockets.broadcast(message)
    return {"ok": True, "message": message}


@app.get("/api/stats")
def stats() -> Dict[str, Any]:
    chat_messages = load_chat_messages()
    summaries = [item for item in load_history() if item.get("topic") == "summary" or item.get("intent") == "summarize"]
    return {
        "question_answer_count": len(load_history()),
        "chat_message_count": len(chat_messages),
        "user_message_count": sum(item.get("role") == "user" for item in chat_messages),
        "assistant_message_count": sum(item.get("role") == "assistant" for item in chat_messages),
        "summary_count": len(summaries),
        "active_reminder_count": len([item for item in load_reminders() if item.get("status") == "active"]),
    }


@app.get("/api/messages")
def messages() -> Dict[str, Any]:
    return {"messages": load_chat_messages()}


@app.get("/api/reminders")
def reminders() -> Dict[str, Any]:
    return {"reminders": load_reminders()}


@app.get("/api/workspace")
def workspace() -> Dict[str, Any]:
    return load_workspace()


@app.post("/api/posts")
async def create_post(request: PostRequest) -> Dict[str, Any]:
    post = append_post(request.channel_id, request.title, request.content, request.author)
    await chat_sockets.broadcast({"event":"post_created", "post":post})
    return {"ok": True, "post": post}


@app.post("/api/post-replies")
async def create_post_reply(request: ReplyRequest) -> Dict[str, Any]:
    try:
        event = append_reply(request.post_id, request.content, request.author)
    except KeyError:
        raise HTTPException(status_code=404, detail="Post not found")
    await chat_sockets.broadcast({"event": "post_reply_created", **event})
    return {"ok": True, **event}


@app.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket) -> None:
    await chat_sockets.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if event.get("event") == "ai_typing" and event.get("channel"):
                await chat_sockets.broadcast(event)
    except WebSocketDisconnect:
        chat_sockets.disconnect(websocket)
    except Exception:
        chat_sockets.disconnect(websocket)
