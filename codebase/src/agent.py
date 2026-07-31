from typing import Any, Callable, Dict, Optional

from history_store import append_question_answer, find_similar_question
from prompt_loader import build_prompt
from text_utils import normalize_text


GenerateFn = Callable[[Dict[str, Any]], Dict[str, Any]]


def classify_question(question: str) -> str:
    text = (question or "").lower()
    normalized = normalize_text(text)

    if "tóm tắt" in text or "tom tat" in normalized or "summar" in normalized or "ngan gon" in normalized:
        return "summarize"
    if any(term in normalized for term in ("lich", "thong bao", "su kien", "calendar", "schedule")):
        return "notifications"
    if any(term in normalized for term in ("o tren", "vua noi", "vua hoi", "ai hoi", "nguoi nao hoi", "doan chat", "tin nhan nay", "dang hoi gi", "dang noi gi")):
        return "context"
    if "đã hỏi" in text or "cau nay" in normalized or "truoc do" in normalized:
        return "history"
    return "answer"


def build_agent_context(question: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    options = options or {}
    requested_intent = options.get("intent")
    detected_intent = classify_question(question)
    # A natural-language summary request must remain a summary even when an
    # older frontend sends the generic answer intent.
    intent = "summarize" if detected_intent == "summarize" else (requested_intent or detected_intent)
    topic = options.get("topic", "general")
    threshold = float(options.get("threshold", 0.4))
    match = find_similar_question(question, threshold=threshold)

    return {
        "intent": intent,
        "topic": topic,
        "threshold": threshold,
        "match": match,
    }


def build_agent_prompt(question: str, context: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    options = options or {}
    selected_messages = options.get("messages", "")

    if context["intent"] == "summarize":
        return build_prompt(
            "summarize",
            {
                "selected_topic": options.get("topic", "chủ đề onboarding"),
                "messages": selected_messages,
            },
        )

    if context["intent"] == "history":
        return build_prompt(
            "retrieve",
            {
                "selected_topic": options.get("topic", "câu hỏi tương tự"),
                "messages": selected_messages,
            },
        )

    return build_prompt("fallback", {"messages": selected_messages})


def agent_respond(
    question: str,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    options = options or {}
    context = build_agent_context(question, options)
    prompt = build_agent_prompt(question, context, options)

    if context["match"] and context["intent"] == "history":
        return {
            "mode": "history",
            "intent": context["intent"],
            "confidence": context["match"]["score"],
            "matched_question": context["match"]["record"]["question"],
            "answer": context["match"]["record"]["answer"],
            "record": context["match"]["record"],
        }

    generate_answer = options.get("generate_answer")
    if not callable(generate_answer):
        return {
            "mode": "needs_generate",
            "intent": context["intent"],
            "confidence": 0,
            "matched_question": None,
            "answer": None,
            "record": None,
        }

    generated = generate_answer(
        {
            "question": question,
            "intent": context["intent"],
            "topic": context["topic"],
            "prompt": prompt,
            "context": context,
        }
    )

    record = append_question_answer(
        {
            "question": question,
            "answer": generated.get("answer", ""),
            "topic": generated.get("topic", context["topic"]),
            "intent": context["intent"],
            "source": generated.get("source", "agent"),
        }
    )

    return {
        "mode": "generated",
        "intent": context["intent"],
        "confidence": generated.get("confidence", 0),
        "matched_question": None,
        "answer": generated.get("answer", ""),
        "record": record,
        "source": generated.get("source", "agent"),
    }

