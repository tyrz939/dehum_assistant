import os
import requests
import json

USE_OPENAI = os.getenv("USE_OPENAI", "true").lower() == "true"

if USE_OPENAI:
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    openai_client = OpenAI(api_key=api_key)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

def stream_completion(messages):
    if USE_OPENAI:
        for chunk in openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            stream=True
        ):
            yield chunk.choices[0].delta.content or ""
    else:
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": os.getenv("OLLAMA_MODEL", "llama2"),
                "messages": messages,
                "stream": True
            },
            stream=True
        )
        for line in response.iter_lines():
            if line:
                try:
                    data = line.decode("utf-8").removeprefix("data: ").strip()
                    parsed = json.loads(data)
                    delta = parsed.get("message", {}).get("content", "")
                    yield delta
                except Exception:
                    continue