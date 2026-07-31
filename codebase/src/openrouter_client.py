import json
import os
from typing import Any, Dict, Optional

import httpx


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b")


def openrouter_generate(
    *,
    api_key: str,
    question: str,
    messages: str,
    prompt: Dict[str, Any],
    model: Optional[str] = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    chosen_model = model or DEFAULT_MODEL
    language_rule = "Trả lời bằng tiếng Việt theo mặc định. Chỉ dùng ngôn ngữ khác nếu người dùng yêu cầu rõ ràng."
    system = f"{language_rule}\n\n{prompt.get('system', '')}\n\n{prompt.get('task', '')}".strip()
    user = (
        f"Câu hỏi: {question}\n\n"
        f"Ngữ cảnh:\n{messages or '(không có)'}\n\n"
        "QUY ĐỊNH BẮT BUỘC: Câu trả lời trong trường answer phải viết bằng tiếng Việt. "
        "Không dùng tiếng Anh nếu người dùng không yêu cầu.\n\n"
        "Giọng trả lời: thân thiện, tự nhiên như đang chat với một học viên. "
        "Trả lời trực tiếp câu hỏi trước; không nói về việc truy xuất context, không nói "
        "'theo bài đăng bạn đã tham khảo', không tự nhận mình đã đọc nguồn nào. "
        "Nếu câu hỏi đơn giản, trả lời 1-3 câu là đủ. Chỉ dùng gạch đầu dòng khi có nhiều ý.\n\n"
        "Chỉ dùng thông tin có trong ngữ cảnh. Nếu ngữ cảnh có kênh hoặc bài đăng nguồn, "
        "hãy ưu tiên nguồn liên quan nhất đến câu hỏi và nêu rõ kênh/bài đăng đó. "
        "Không gán một nguồn chỉ vì có cùng từ khóa chung như API.\n\n"
        "Chỉ trả về JSON hợp lệ theo schema này:\n"
        '{"answer":"string", "confidence":0.0, "summary":"string"}'
    )
    payload = {
        "model": chosen_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "K4 Conversation Summarizer",
    }

    with httpx.Client(timeout=timeout) as client:
        response = client.post(OPENROUTER_URL, json=payload, headers=headers)
        if response.is_error:
            detail = response.text[:300].replace("\n", " ")
            raise RuntimeError(f"OpenRouter API error {response.status_code}: {detail}")
        data = response.json()

    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("OpenRouter returned no choices.")
    text = choices[0].get("message", {}).get("content", "").strip()
    if not text:
        raise RuntimeError("OpenRouter returned empty content.")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = {"answer": text}
    return {"raw": data, "parsed": parsed, "model": chosen_model}
