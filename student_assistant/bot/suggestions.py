import json
import os

from aiofile import async_open

SUGGESTIONS_LOG = os.getenv("SUGGESTIONS_LOG", "suggestions.jsonl")


async def save_suggestion(data: dict):
    async with async_open(SUGGESTIONS_LOG, encoding='utf-8', mode='a') as f:
        payload = json.dumps(data, ensure_ascii=False)
        await f.write(payload)
        await f.write("\n")


async def get_all_suggestions() -> list[dict]:
    async with async_open(SUGGESTIONS_LOG, encoding='utf-8', mode='r') as f:
        payload = await f.read()
        data = [json.loads(line) for line in payload.splitlines()]
        return data
