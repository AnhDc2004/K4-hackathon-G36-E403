import json
from pathlib import Path
from typing import Any, Dict


BASE_DIR = Path(__file__).resolve().parent
PROMPT_DIR = BASE_DIR.parent / "prompts"


def load_prompt(name: str) -> Dict[str, Any]:
    prompt_path = PROMPT_DIR / f"{name}.json"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {name}")

    with prompt_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def render_template(template: str, variables: Dict[str, Any] | None = None) -> str:
    variables = variables or {}

    def replace(match):
        key = match.group(1)
        value = variables.get(key)
        return "" if value is None else str(value)

    import re

    return re.sub(r"\{\{(\w+)\}\}", replace, template)


def build_prompt(name: str, variables: Dict[str, Any] | None = None) -> Dict[str, Any]:
    prompt = load_prompt(name)
    variables = variables or {}

    return {
        "name": prompt.get("name", name),
        "description": prompt.get("description", ""),
        "system": render_template(prompt.get("system", ""), variables),
        "task": render_template(prompt.get("task", ""), variables),
        "output_format": prompt.get("output_format", {}),
    }

