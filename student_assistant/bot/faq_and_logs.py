import json

from aiofile import async_open

async def save_requests(data: dict):
    # перезаписывает в файл
    async with async_open('student_assistant/bot/requests.jsonl', encoding='utf-8', mode='a') as f:
        payload = json.dumps(data, ensure_ascii=False)
        await f.write(payload)
        await f.write("\n")

async def get_possible_options() -> list[dict]:
    async with async_open('student_assistant/bot/faq.json', encoding='utf-8', mode='r') as f:
        payload = await f.read()
        config_data = json.loads(payload)
        return config_data
