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
from workspace_store import append_post, load_workspace, search_workspace
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
    intent: Optional[str] = Field(default=None, pattern="^(answer|history|summarize)$")


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


def parse_reminder(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"nhắc\s+(?:tôi|mình)\s+(\d+)\s+phút\s+trước(?:\s+khi)?\s+(.+)", text, re.IGNORECASE)
    if not match:
        return None
    event = match.group(2).strip().rstrip(".!?")
    return {"minutes_before": int(match.group(1)), "event": event}


def format_history_context(history: Optional[List[Dict[str, Any]]], messages: str) -> str:
    if history:
        lines = []
        for item in history:
            author = item.get("author") or item.get("a") or "Unknown"
            text = item.get("text") or item.get("m") or ""
            time = item.get("time") or item.get("t") or ""
            lines.append(f"- {author} | {time} | {text}")
        return "\n".join(lines)
    return messages or ""


def build_grounded_context(question: str, history: Optional[List[Dict[str, Any]]], messages: str) -> tuple[str, List[Dict[str, Any]]]:
    matches = search_workspace(question)
    source_lines = []
    for item in matches:
        source_lines.append(
            f"[SOURCE id={item['id']} url={item['source_url']}] "
            f"{item.get('title', item.get('author', ''))}: {item.get('content', '')}"
        )
        for reply in item.get("replies", []):
            source_lines.append(f"[SOURCE id={item['id']} url={item['source_url']}] {reply.get('author')}: {reply.get('content')}")
    context = "Nguồn workspace ưu tiên:\n" + "\n".join(source_lines) if source_lines else ""
    provided = format_history_context(history, messages)
    normalized_question = normalize_text(question)
    if "tom tat" in normalized_question or "summarize" in normalized_question or "summary" in normalized_question:
        saved = load_chat_messages()
        saved_context = "\n".join(
            f"- {item.get('username', 'Người dùng')} | {item.get('channel', '')} | {item.get('content', '')}"
            for item in saved[-200:]
            if item.get("content")
        )
        provided = f"Hội thoại đã lưu:\n{saved_context}\n\nContext hiện tại:\n{provided}"
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
    combined_messages, matches = build_grounded_context(request.question, request.history, request.messages)
    intent = request.intent or classify_question(request.question)
    if intent == "answer":
        answered = next((item for item in matches if item.get("type") == "post" and item.get("replies")), None)
        if answered:
            answer = "\n".join(reply.get("content", "") for reply in answered["replies"] if reply.get("content"))
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


@app.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket) -> None:
    await chat_sockets.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        chat_sockets.disconnect(websocket)
    except Exception:
        chat_sockets.disconnect(websocket)
