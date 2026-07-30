from typing import Any, Callable, Dict, Optional

from history_store import append_question_answer, find_similar_question
from prompt_loader import build_prompt


GenerateFn = Callable[[Dict[str, Any]], Dict[str, Any]]


def classify_question(question: str) -> str:
    text = (question or "").lower()

    if "tóm tắt" in text or "summary" in text or "ngắn gọn" in text:
        return "summarize"
    if "đã hỏi" in text or "câu này" in text or "trước đó" in text:
        return "history"
    return "answer"


def build_agent_context(question: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    options = options or {}
    intent = options.get("intent") or classify_question(question)
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

    if context["match"]:
        return {
            "mode": "history",
            "intent": context["intent"],
            "confidence": context["match"]["score"],
            "matched_question": context["match"]["record"]["question"],
            "answer": context["match"]["record"]["answer"],
            "prompt": prompt,
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
            "prompt": prompt,
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
            "source": generated.get("source", "agent"),
        }
    )

    return {
        "mode": "generated",
        "intent": context["intent"],
        "confidence": generated.get("confidence", 0),
        "matched_question": None,
        "answer": generated.get("answer", ""),
        "prompt": prompt,
        "record": record,
    }

