import json
import os
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv


GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
load_dotenv()
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _build_contents(question: str, messages: str, prompt: Dict[str, Any]) -> List[Dict[str, Any]]:
    user_parts = [
        {
            "text": (
                f"Câu hỏi: {question}\n\n"
                f"Ngữ cảnh:\n{messages or '(không có)'}\n\n"
                f"Yêu cầu đầu ra:\n{json.dumps(prompt.get('output_format', {}), ensure_ascii=False)}"
            )
        }
    ]

    return [{"role": "user", "parts": user_parts}]


def gemini_generate(
    *,
    api_key: str,
    question: str,
    messages: str,
    prompt: Dict[str, Any],
    model: Optional[str] = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    chosen_model = model or DEFAULT_MODEL
    url = GEMINI_API_URL.format(model=chosen_model)

    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": f"{prompt.get('system', '')}\n\n{prompt.get('task', '')}"
                }
            ]
        },
        "contents": _build_contents(question, messages, prompt),
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload, headers=headers)
        if response.is_error:
            detail = response.text[:300].replace("\n", " ")
            raise RuntimeError(f"Gemini API error {response.status_code}: {detail}")
        data = response.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates.")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise RuntimeError("Gemini returned empty text.")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = {"answer": text}

    return {
        "raw": data,
        "parsed": parsed,
        "model": chosen_model,
    }
