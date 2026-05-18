# Sprint 5 — Артём Филиппов + Лев Абросимов

## Голосовой сервер: финализация

В Sprint 4 вы подняли FastAPI сервер с Whisper + Silero TTS. Сейчас он работает у вас на маках, но у других студентов при попытке запустить сломается из-за мелочей. Доводите до состояния «запустится у любого».

## Артём — `voice_server.py`

### 1) Валидация входа — УЖЕ СДЕЛАНО

У тебя в `/ask` уже есть проверка `allowed_content_types` (audio/wav, audio/webm и т.д.) с возвратом 400. Это хорошо — оставь как есть, ничего менять не нужно.

### 2) НЕ ТРОГАЙ блок `@app.on_event("startup")`

Там грузятся две модели:
- **Whisper** — распознаёт речь и превращает в текст
- **Silero TTS** — наоборот, текст превращает в голос

Они грузятся один раз при старте сервера и потом висят в RAM. Если случайно удалишь — каждый запрос будет ждать загрузки моделей 30 секунд. Просто проверь что этот блок на месте и работает.

### 3) Интеграция с Андреем (формулы)

Если ответ из FAQ содержит формулу типа `$E=mc^2$`, надо красиво её показать. Договоритесь с Андреем:
- У Андрея сервис в Docker мапится на хост-порт **8001** (внутри контейнера — 8000)
- Ты дёргаешь `http://localhost:8001/render`
- Принимает JSON `{"latex": "E=mc^2"}`, возвращает PNG (Content-Type: image/png)
- Ты в `/ask` после получения текста ответа проверяешь регуляркой есть ли `$...$`, если есть — дёргаешь Андрея, получаешь PNG, кодируешь в base64, кладёшь в ответ как поле `image_base64`

**Важно про порты:** твой сервер слушает 8000, Андрея — 8001. Если Андрей запускает БЕЗ Docker (просто `uvicorn`), его default тоже 8000 — конфликт. Договорись чтобы он запускал через `docker compose up` (тогда снаружи 8001) ИЛИ ставил `--port 8001` для uvicorn.

Если Андрей не успеет — пропусти этот пункт, не блокируй сдачу.

### 4) Дальнейшие правки — только через PR

Сейчас твой `voice_server.py` уже в `main` (через прямой пуш с ветки Vondre — так больше не делаем). Если будешь что-то править ещё — работай в ветке `team-artem-lev` и через Pull Request, не пуши в main напрямую.

## Лев — слить ветку в main + тесты + README

### 1) ⚠️ Главное — слить `team-artem-lev` в main

Сейчас в твоей ветке `team-artem-lev` лежит **куча твоей работы**: `test_voice.py`, `test_audios/`, `requirements.txt`, `.gitignore`, `Readme.Md`, `handlers/`, `keyboards/`, `suggestions.py`, `faq.json`. **В main ничего этого нет** — Артём пушил свой `voice_server.py` напрямую, твоя работа осталась в ветке.

Что делать:
```bash
git checkout team-artem-lev
git fetch origin
git rebase origin/main
# Будет конфликт в voice_server.py — выбери версию из main (она актуальнее, чем у тебя в ветке)
git rebase --continue
git push --force-with-lease origin team-artem-lev
```

Потом создай Pull Request из `team-artem-lev` в `main` через GitHub. Ревьюит кто-то из группы, потом мердж.

После мерджа в main попадут все твои файлы.

### 2) Переименуй `Readme.Md` → `README.md`

У тебя файл назван `Readme.Md` (странный регистр) — это стандарт GitHub `README.md`, переименуй:
```bash
git mv student_assistant/bot/Readme.Md student_assistant/bot/README.md
```

### 3) Допиши два теста на ошибки

Открой `test_voice.py`, добавь:

```python
def test_ask_no_file(client):
    """Запрос без файла должен вернуть ошибку, а не упасть"""
    response = client.post("/ask")
    assert response.status_code in (400, 422)

def test_ask_wrong_type(client):
    """Текстовый файл вместо аудио должен вернуть 400 (allowed_content_types не содержит text/plain)"""
    response = client.post(
        "/ask",
        files={"file": ("a.txt", b"hello", "text/plain")}
    )
    assert response.status_code == 400
```

**Как проверить:** `pytest test_voice.py -v` — все тесты должны быть зелёные.

### 4) Финализируй README.md

У тебя уже есть `Readme.Md` в ветке — обнови его (после переименования) до такой структуры:

```markdown
# Голосовой сервер ассистента

Принимает аудио, распознаёт речь, ищет ответ в FAQ, синтезирует голосовой ответ.

## Что поставить заранее

- Python 3.10+
- ffmpeg (системная утилита, не python-пакет):
  - mac: `brew install ffmpeg`
  - ubuntu: `sudo apt install ffmpeg`
  - windows: https://www.gyan.dev/ffmpeg/builds/ → скачать, добавить в PATH

## Установка

pip install -r requirements.txt

При первом запуске сервер скачает модели Whisper (~500MB) и Silero (~100MB) — это нормально.

## Запуск

uvicorn voice_server:app

## Проверка

curl http://localhost:8000/health
# Должно вернуть {"status": "ok"}

## Тесты

pytest test_voice.py
```

### 5) `.env.example`

Положи рядом с `voice_server.py`:
```
WHISPER_MODEL=small
```

## Результат: что лежит в папке

```
student_assistant/bot/
├── voice_server.py       # FastAPI сервер (Артём)
├── test_voice.py         # тесты (Лев)
├── search_engine.py      # из Sprint 3-4
├── handlers/             # из Sprint 3
├── faq.json              # база знаний
├── test_audios/          # тестовые аудио для pytest
├── requirements.txt
├── .env.example          # WHISPER_MODEL=small
├── .gitignore            # .env, __pycache__/
└── README.md             # инструкция (Лев)
```

## Как проверяется

1. Другой студент клонирует репо, ставит ffmpeg по README
2. `pip install -r requirements.txt`
3. `uvicorn voice_server:app` — сервер стартует без ошибок
4. `curl http://localhost:8000/health` → `{"status": "ok"}`
5. `pytest test_voice.py` — все тесты зелёные
6. POST на `/ask` с WAV-файлом — возвращает JSON с `question`, `answer`, `audio_base64`

## Если застрял

Спрашивайте друг друга, других студентов или Сергея Романовича в чате — но не молчите две недели.
