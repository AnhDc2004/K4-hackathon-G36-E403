import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from agent import agent_respond
from gemini_client import gemini_generate


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


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Câu hỏi của học viên")
    topic: Optional[str] = Field(default="general", description="Chủ đề onboarding")
    messages: Optional[str] = Field(default="", description="Ngữ cảnh tin nhắn liên quan")
    threshold: Optional[float] = Field(default=0.4, ge=0.0, le=1.0)
    history: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Lịch sử chat hoặc bài đăng liên quan"
    )


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


def gemini_generate_answer(payload: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY environment variable.")

    if os.getenv("EVAL_OFFLINE") == "1":
        question = payload["question"]
        topic = payload.get("topic", "general")
        return {
            "answer": f'Offline eval: "{question}" | topic={topic}',
            "topic": topic,
            "confidence": 0.0,
            "source": "offline-fallback",
            "model": os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            "parsed": {"offline": True},
        }

    try:
        result = gemini_generate(
            api_key=api_key,
            question=payload["question"],
            messages=payload.get("messages", ""),
            prompt=payload.get("prompt", {}),
            model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
        )

        parsed = result.get("parsed", {})
        answer = parsed.get("answer") or parsed.get("response") or parsed.get("summary") or ""

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
        return {
            "answer": f'Fallback local: chưa gọi được Gemini cho "{question}" | topic={topic}',
            "topic": topic,
            "confidence": 0.0,
            "source": "fallback",
            "model": os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            "parsed": {"error": str(exc)},
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
    combined_messages = format_history_context(request.history, request.messages)
    result = agent_respond(
        request.question,
        {
            "topic": request.topic,
            "messages": combined_messages,
            "threshold": request.threshold,
            "generate_answer": gemini_generate_answer,
        },
    )

    return result


@app.post("/api/assistant")
def assistant(request: ChatRequest) -> Dict[str, Any]:
    combined_messages = format_history_context(request.history, request.messages)
    result = agent_respond(
        request.question,
        {
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
        "prompt": result.get("prompt"),
        "record": result.get("record"),
    }
