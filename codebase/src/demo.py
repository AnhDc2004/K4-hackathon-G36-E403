import json

from agent import agent_respond


def fake_generate_answer(payload):
    return {
        "answer": f'AI agent đã tạo câu trả lời mới cho: "{payload["question"]}" | intent={payload["intent"]} | topic={payload["topic"]}',
        "topic": payload["topic"],
        "confidence": 0.72,
        "source": "mock-llm",
    }


result = agent_respond(
    "Em nộp bài ở đâu?",
    {
        "topic": "submission",
        "messages": "- M001: Bài nộp ở mục Assignments.\n- M002: Hạn nộp là thứ Hai.",
        "generate_answer": fake_generate_answer,
    },
)

print(json.dumps(result, ensure_ascii=False, indent=2))
