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

1. **Конвертация аудио** — браузер присылает `audio/webm`, Whisper ожидает WAV. Конвертировать через ffmpeg:
   ```python
   import subprocess, tempfile, os

   def webm_to_wav(input_path: str) -> str:
       output_path = input_path.replace(".webm", ".wav")
       subprocess.run(["ffmpeg", "-y", "-i", input_path, output_path],
                      check=True, capture_output=True)
       return output_path
   ```
   ffmpeg должен быть установлен: `brew install ffmpeg` / `apt install ffmpeg`

2. **Whisper STT** — аудио → текст вопроса
   ```python
   import whisper
   model = whisper.load_model("small")  # small для скорости
   result = model.transcribe(wav_path, language="ru")
   question = result["text"]
   ```

3. **search_engine** — текст → ответ из faq.json (ваш модуль из Sprint 3)

4. **Silero TTS** — ответ → аудио. `apply_tts()` возвращает torch.Tensor — его нужно конвертировать в байты:
   ```python
   import torch, io, scipy.io.wavfile as wav
   import numpy as np

   tts_model, _ = torch.hub.load('snakers4/silero-models',
                                   'silero_tts', language='ru', speaker='v3_1_ru')
   audio_tensor = tts_model.apply_tts(text=answer, speaker='aidar', sample_rate=48000)

   buf = io.BytesIO()
   wav.write(buf, 48000, audio_tensor.numpy())
   audio_bytes = buf.getvalue()
   ```

5. Вернуть `audio_base64` через `base64.b64encode(audio_bytes).decode()`

### CORS — обязательно

Фронтенд работает на `localhost:3000`, бэкенд на `localhost:8000` — браузер заблокирует запросы без CORS:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"])
```

### Артём

- Реализует `voice_server.py` (FastAPI + пайплайн + CORS)
- Оборачивает `search_engine.py` в функцию пригодную для вызова из сервера
- Тестирует через `curl` или Postman

### Лев

- Пишет `requirements.txt` для голосового сервера (whisper, torch, silero, scipy, ffmpeg-python, fastapi, uvicorn)
- Пишет `README.md`: как установить ffmpeg и зависимости, как запустить сервер
- Пишет `test_voice.py` — автотест: отправить тестовый WAV-файл на `/ask`, проверить что в ответе есть поля `question`, `answer`, `audio_base64`
- Тестирует end-to-end: записать wav → отправить → получить ответ

## Результат: что лежит в папке

```
student_assistant/bot/
├── voice_server.py       # FastAPI сервер (новое)
├── test_voice.py         # автотест endpoint /ask (новое, Лев)
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
