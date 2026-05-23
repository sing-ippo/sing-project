import json
import os

from aiofile import async_open

FAQ_PATH = os.getenv("FAQ_PATH", "faq.json")
REQUESTS_LOG = os.getenv("REQUESTS_LOG", "requests.jsonl")


async def save_requests(data: dict):
    async with async_open(REQUESTS_LOG, encoding='utf-8', mode='a') as f:
        payload = json.dumps(data, ensure_ascii=False)
        await f.write(payload)
        await f.write("\n")


async def get_possible_options() -> list[dict]:
    async with async_open(FAQ_PATH, encoding='utf-8', mode='r') as f:
        payload = await f.read()
        config_data = json.loads(payload)
        return config_data
