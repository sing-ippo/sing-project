# Бот преподавателя — генерация квизов

Telegram-бот: загружаешь документ (.txt/.pdf/.docx) или выбираешь категорию из базы знаний — бот генерирует тест с вопросами A/B/C/D через DeepSeek и проводит его с подсчётом баллов.

## Команды
- `/start` — приветствие и режимы
- `/categories` — выбрать категорию из базы знаний (кнопками)
- `/quiz_faq <категория>` — квиз по категории (напр. `/quiz_faq Python`)
- Прислать файл `.txt/.pdf/.docx` — квиз по документу

## Что нужно
1. **Telegram-токен** — у @BotFather (`/newbot`).
2. **Ключ DeepSeek** — platform.deepseek.com → API keys.

## Запуск (локально)
```bash
pip install -r requirements.txt
cp .env.example .env   # заполнить TELEGRAM_TOKEN и DEEPSEEK_API_KEY
python teacher_bot.py
```

## Запуск (Docker, из корня репо)
```bash
docker compose up -d teacher_bot
```
Переменные берутся из корневого `.env` (`TELEGRAM_TOKEN`, `DEEPSEEK_API_KEY`, ...).

## Формат квиза
`{id, question, options[4], correct (0–3), explanation, source_chunk_id}` — генерируется DeepSeek, нормализуется в `pipeline.py`.
