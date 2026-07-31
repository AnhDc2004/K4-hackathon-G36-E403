import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from text_utils import normalize_text, tokenize


BASE_DIR = Path(__file__).resolve().parent
HISTORY_PATH = BASE_DIR.parent / "data" / "question_history.json"
CHAT_LOG_PATH = BASE_DIR.parent / "data" / "chat_history.jsonl"
REMINDER_PATH = BASE_DIR.parent / "data" / "reminders.json"


def ensure_history_file() -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not HISTORY_PATH.exists():
        HISTORY_PATH.write_text("[]\n", encoding="utf-8")


def load_history() -> List[Dict[str, Any]]:
    ensure_history_file()
    data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def save_history(records: List[Dict[str, Any]]) -> None:
    ensure_history_file()
    HISTORY_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def similarity_score(query: str, candidate: str) -> float:
    query_tokens = set(tokenize(query))
    candidate_tokens = set(tokenize(candidate))

    if not query_tokens or not candidate_tokens:
        return 0.0

    overlap = len(query_tokens & candidate_tokens)
    return overlap / max(len(query_tokens), len(candidate_tokens))


def find_similar_question(question: str, threshold: float = 0.4) -> Optional[Dict[str, Any]]:
    history = load_history()
    normalized_question = normalize_text(question)

    best_record = None
    best_score = 0.0

    for record in history:
        # Failed/offline generations are diagnostics, never reusable answers.
        if record.get("source") in {"fallback", "offline-fallback", "gemini-error"}:
            continue
        candidate = record.get("normalized_question") or record.get("question", "")
        score = max(
            similarity_score(normalized_question, candidate),
            similarity_score(question, record.get("question", "")),
        )

        if score > best_score:
            best_score = score
            best_record = record

    if best_record is None or best_score < threshold:
        return None

    return {
        "record": best_record,
        "score": round(best_score, 3),
    }


def append_question_answer(entry: Dict[str, Any]) -> Dict[str, Any]:
    history = load_history()
    record_id = entry.get("id") or f"q{len(history) + 1:03d}"

    record = {
        "id": record_id,
        "question": entry.get("question", ""),
        "normalized_question": entry.get("normalized_question") or normalize_text(entry.get("question", "")),
        "answer": entry.get("answer", ""),
        "topic": entry.get("topic", "general"),
        "created_at": entry.get("created_at") or datetime.now(timezone.utc).isoformat(),
        "source": entry.get("source", "llm"),
        "intent": entry.get("intent", "answer"),
        "similar_questions": entry.get("similar_questions", []),
    }

    history.append(record)
    save_history(history)
    return record


def append_chat_message(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Append a chat event without making it part of question retrieval."""
    CHAT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "id": entry.get("id") or f"m-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        "role": entry.get("role", "user"),
        "username": entry.get("username", "Hoàng"),
        "content": entry.get("content", ""),
        "channel": entry.get("channel", "chat-chung"),
        "created_at": entry.get("created_at") or datetime.now(timezone.utc).isoformat(),
    }
    with CHAT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_chat_messages() -> List[Dict[str, Any]]:
    if not CHAT_LOG_PATH.exists():
        return []
    records = []
    for line in CHAT_LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            item.setdefault("username", "Trợ lý AI" if item.get("role") == "assistant" else "Hoàng")
            records.append(item)
    return records


def load_reminders() -> List[Dict[str, Any]]:
    if not REMINDER_PATH.exists():
        return []
    try:
        data = json.loads(REMINDER_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def append_reminder(entry: Dict[str, Any]) -> Dict[str, Any]:
    reminders = load_reminders()
    record = {
        "id": f"r-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        "username": entry.get("username", "Hoàng"),
        "minutes_before": entry["minutes_before"],
        "event": entry["event"],
        "scope": entry.get("scope", "matching_events"),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    reminders.append(record)
    REMINDER_PATH.write_text(json.dumps(reminders, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record

