# Sprint 4 — Артём Филиппов + Лев Абросимов

## Голосовой бэкенд киоска

Вы делаете сердце всего стенда — FastAPI сервер, который принимает аудио, распознаёт речь, ищет ответ и возвращает голосовой ответ.

## Что нужно сделать

### Новый файл: `voice_server.py`

FastAPI сервер с одним главным endpoint:

**POST `/ask`**
- Принимает: аудиофайл (multipart/form-data, wav/webm)
- Возвращает:
```json
{
  "question": "когда день открытых дверей?",
  "answer": "День открытых дверей проходит...",
  "audio_base64": "base64-encoded mp3"
}
```

**GET `/health`**
```json
{ "status": "ok" }
```

### Пайплайн внутри `/ask`

1. **Whisper STT** — аудио → текст вопроса
   ```python
   import whisper
   model = whisper.load_model("small")  # small для скорости
   result = model.transcribe(audio_path, language="ru")
   ```

2. **search_engine** — текст → ответ из faq.json (ваш модуль из Sprint 3)

3. **Silero TTS** — ответ → аудио
   ```python
   import torch
   model, _ = torch.hub.load(repo_or_dir='snakers4/silero-models',
                               model='silero_tts', language='ru', speaker='v3_1_ru')
   audio = model.apply_tts(text=answer, speaker='aidar', sample_rate=48000)
   ```

4. Вернуть `audio_base64` через `base64.b64encode(audio_bytes)`

### Артём

- Реализует `voice_server.py` (FastAPI + пайплайн)
- Оборачивает `search_engine.py` в функцию пригодную для вызова из сервера
- Тестирует через `curl` или Postman

### Лев

- Пишет `requirements.txt` для голосового сервера
- Пишет `README.md`: как установить Whisper и Silero, как запустить сервер
- Тестирует end-to-end: записать wav → отправить → получить ответ

## Результат: что лежит в папке

```
student_assistant/bot/
├── voice_server.py       # FastAPI сервер (новое)
├── search_engine.py      # из Sprint 3
├── suggestions.py        # из Sprint 3
├── handlers/             # из Sprint 3
├── faq.json              # база знаний
├── .env.example          # BOT_TOKEN, WHISPER_MODEL=small
└── README.md             # обновлённый: запуск бота + сервера
```

## Как проверяется

1. `uvicorn voice_server:app --reload` — запускается без ошибок
2. `GET /health` → `{"status": "ok"}`
3. Отправить wav с вопросом → получить JSON с question, answer, audio_base64
4. audio_base64 декодировать → воспроизвести → слышен голосовой ответ на русском
