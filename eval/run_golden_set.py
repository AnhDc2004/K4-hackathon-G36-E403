#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "codebase" / "src"
EVAL_DIR = ROOT / "eval"
RESULTS_DIR = EVAL_DIR / "results"

sys.path.insert(0, str(SRC_DIR))

import main  # noqa: E402


def load_golden_set() -> List[Dict[str, Any]]:
    with (EVAL_DIR / "golden-set.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_history(context: List[str]) -> List[Dict[str, str]]:
    history = []
    for idx, line in enumerate(context):
        text = line.strip()
        if not text:
            continue

        author = "Unknown"
        message = text
        if ":" in text:
            author, message = text.split(":", 1)
            author = author.strip() or "Unknown"
            message = message.strip()

        history.append(
            {
                "a": author,
                "m": message,
                "t": f"ctx-{idx + 1}",
            }
        )
    return history


def expected_keywords(case: Dict[str, Any]) -> List[str]:
    text = " ".join(
        [
            case.get("expected_behavior", ""),
            " ".join(case.get("pass_criteria", [])),
            case.get("topic", ""),
            case.get("input", ""),
        ]
    )
    keywords = []
    for token in re.findall(r"[A-Za-zÀ-ỹ0-9#@/_\-]{3,}", text):
        token = token.strip()
        if len(token) >= 3:
            keywords.append(token)
    unique = []
    for token in keywords:
        if token.lower() not in {x.lower() for x in unique}:
            unique.append(token)
    return unique[:12]


def judge_case(case: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
    answer = response.get("answer") or ""
    mode = response.get("mode") or ""
    matched_question = response.get("matched_question")
    confidence = response.get("confidence", 0)

    keywords = expected_keywords(case)
    hits = [kw for kw in keywords if kw.lower() in answer.lower()]

    layer = case.get("layer", "")
    should_flag_conflict = "mau-thuan" in layer
    should_flag_missing = "mo-ho" in layer
    should_flag_outside = "ngoai-pham-vi" in layer
    should_summarize = "tom-tat" in layer
    should_use_history = case.get("id") in {"case-01", "case-02", "case-12"}

    strict_case = case.get("id") in {"case-26", "case-27", "case-28", "case-29", "case-30"}

    def has_any(text: str, options: List[str]) -> bool:
        lower = text.lower()
        return any(opt in lower for opt in options)

    missing_ok = not should_flag_missing or has_any(answer, ["thiếu", "chưa đủ", "không đủ", "cần thêm", "cung cấp", "yêu cầu"])
    conflict_ok = not should_flag_conflict or has_any(answer, ["mâu thuẫn", "không nhất quán", "kiểm tra lại", "không chọn"])
    outside_ok = not should_flag_outside or has_any(answer, ["không thể", "không có quyền", "vượt phạm vi", "không hỗ trợ", "không làm"])
    summarize_ok = not should_summarize or len(answer.splitlines()) <= 12
    history_ok = not should_use_history or (mode == "history" or matched_question is not None)

    score = 0
    score += 1 if len(answer.strip()) > 0 else 0
    score += 1 if len(hits) >= max(1, min(3, len(keywords) // 4 or 1)) else 0
    score += 1 if missing_ok else 0
    score += 1 if conflict_ok else 0
    score += 1 if outside_ok else 0
    score += 1 if history_ok else 0
    score += 1 if summarize_ok else 0
    score += 1 if confidence is not None else 0

    max_score = 8
    if strict_case:
        passed = bool(answer.strip()) and missing_ok and conflict_ok and outside_ok and summarize_ok and history_ok and len(hits) >= 1
    else:
        passed = score >= 5
    return {
        "score": score,
        "max_score": max_score,
        "passed": passed,
        "keywords_hit": hits,
    }


def run_case(case: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "question": case["input"],
        "topic": case.get("topic", "general"),
        "messages": "\n".join(case.get("context", [])),
        "threshold": 0.4,
        "history": parse_history(case.get("context", [])),
    }
    request = main.ChatRequest(**payload)
    data = main.assistant(request)
    judgment = judge_case(case, data)
    return {
        "id": case["id"],
        "topic": case.get("topic"),
        "layer": case.get("layer"),
        "input": case.get("input"),
        "expected_behavior": case.get("expected_behavior"),
        "pass_criteria": case.get("pass_criteria"),
        "response": data,
        "judgment": judgment,
    }


def main_run() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cases = load_golden_set()
    results = [run_case(case) for case in cases]
    passed = sum(1 for r in results if r["judgment"]["passed"])
    total = len(results)
    percent = round((passed / total * 100) if total else 0, 1)

    run_name = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    out_path = RESULTS_DIR / f"{run_name}.json"
    summary_path = RESULTS_DIR / f"{run_name}.md"

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "run_name": run_name,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "passed": passed,
                "total": total,
                "percent": percent,
                "results": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    lines = [
        f"# Golden Set Run {run_name}",
        "",
        f"- Passed: {passed}/{total}",
        f"- Pass rate: {percent}%",
        "",
        "| Case | Layer | Score | Pass | Mode | Answer Preview |",
        "|---|---|---:|:---:|---|---|",
    ]
    for r in results:
        answer = (r["response"].get("answer") or "").replace("\n", " ")
        answer = answer[:90] + ("..." if len(answer) > 90 else "")
        lines.append(
            f"| {r['id']} | {r['layer']} | {r['judgment']['score']}/{r['judgment']['max_score']} | "
            f"{'✅' if r['judgment']['passed'] else '❌'} | {r['response'].get('mode', '')} | {answer} |"
        )

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Run saved to: {out_path}")
    print(f"Summary saved to: {summary_path}")
    print(f"Passed: {passed}/{total} ({percent}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_run())
