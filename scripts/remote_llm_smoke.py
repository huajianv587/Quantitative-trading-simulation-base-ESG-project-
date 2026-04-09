from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")


def main() -> int:
    base_url = os.getenv("REMOTE_LLM_URL", "http://127.0.0.1:8010").rstrip("/")
    api_key = os.getenv("REMOTE_LLM_API_KEY", "")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    result: dict[str, object] = {
        "remote_llm_url": base_url,
    }

    health = requests.get(f"{base_url}/health", timeout=15)
    result["health_status"] = health.status_code
    result["health_body"] = health.json()

    chat = requests.post(
        f"{base_url}/chat",
        headers=headers,
        json={
            "messages": [
                {"role": "system", "content": "You are an ESG analyst."},
                {"role": "user", "content": "Summarize Tesla ESG priorities in 3 bullets."},
            ],
            "max_tokens": 128,
            "temperature": 0.0,
        },
        timeout=180,
    )
    result["chat_status"] = chat.status_code
    result["chat_body"] = chat.json() if chat.headers.get("content-type", "").startswith("application/json") else chat.text

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if chat.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
