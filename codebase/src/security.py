import re
from typing import Any, Dict


INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(all|previous|above)|bỏ qua\s+(mọi|tất cả)|reveal\s+(the\s+)?system|show\s+(me\s+)?the\s+prompt|system\s+prompt|developer\s+message|api[_ -]?key|password|mật khẩu|token|secret|credential|thông tin đăng nhập)",
    re.IGNORECASE,
)
SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bsk-or-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"),
]


def security_check(text: str) -> Dict[str, Any]:
    value = str(text or "")
    if len(value) > 5000:
        return {"blocked": True, "reason": "input_too_large"}
    if INJECTION_PATTERNS.search(value):
        return {"blocked": True, "reason": "sensitive_or_prompt_injection"}
    return {"blocked": False, "reason": None}


def redact_sensitive(value: str) -> str:
    result = str(value or "")
    for pattern in SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result
