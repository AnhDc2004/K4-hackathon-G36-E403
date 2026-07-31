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


def search_workspace(query: str, limit: int = 5, channel_ids: set[str] | None = None) -> List[Dict[str, Any]]:
    clean_query = normalize_text(query).replace("tro ly ai", " ")
    tokens = {token for token in tokenize(clean_query) if len(token) >= 2}
    ranked = []
    for item in load_workspace()["items"]:
        if channel_ids and item.get("channel_id") not in channel_ids:
            continue
        title = normalize_text(item.get("title", ""))
        text = normalize_text(" ".join([item.get("title", ""), item.get("content", ""), *[r.get("content", "") for r in item.get("replies", [])]]))
        candidate_tokens = set(tokenize(text))
        title_tokens = set(tokenize(title))
        score = len(tokens & candidate_tokens) + (2 * len(tokens & title_tokens))
        if clean_query in text or title in clean_query:
            score += 8
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


def append_reply(post_id: str, content: str, author: str) -> Dict[str, Any]:
    data = load_workspace()
    target = next(
        (item for item in data["items"]
         if item.get("type") == "post" and (item.get("id") == post_id or item.get("id", "").endswith(f"-{post_id}"))),
        None,
    )
    if target is None:
        raise KeyError(post_id)
    reply = {"author": author, "content": content, "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
    target.setdefault("replies", []).append(reply)
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"post_id": target["id"], "reply": reply}
