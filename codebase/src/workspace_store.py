import json
from pathlib import Path
from typing import Any, Dict, List

from text_utils import normalize_text, tokenize


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "workspace.json"


def load_workspace() -> Dict[str, Any]:
    with DATA_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError("workspace.json must contain an items list")
    return data


def search_workspace(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    tokens = {token for token in tokenize(query) if len(token) >= 2}
    ranked = []
    for item in load_workspace()["items"]:
        text = normalize_text(" ".join([item.get("title", ""), item.get("content", ""), *[r.get("content", "") for r in item.get("replies", [])]]))
        candidate_tokens = set(tokenize(text))
        score = len(tokens & candidate_tokens)
        if normalize_text(query) in text:
            score += 2
        # One common word such as "hôm nay" is not enough evidence.
        if score >= 2:
            ranked.append((score, item))
    return [item for _, item in sorted(ranked, key=lambda row: row[0], reverse=True)[:limit]]


def append_post(channel_id: str, title: str, content: str, author: str) -> Dict[str, Any]:
    data = load_workspace()
    post_number = sum(1 for item in data["items"] if item.get("type") == "post") + 1
    post = {
        "id": f"post-{channel_id}-{post_number}",
        "channel_id": channel_id,
        "type": "post",
        "title": title,
        "author": author,
        "content": content,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "source_url": f"/#channel/{channel_id}/post/post-{channel_id}-{post_number}",
        "replies": [],
    }
    data["items"].insert(0, post)
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return post
