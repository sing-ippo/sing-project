"""Веб-API генератора квизов для преподавателей (без Telegram).
Один эндпоинт: браузер шлёт текст ИЛИ файл (+ необязательно страницы/тему) →
DeepSeek генерит квиз → отдаём JSON + meta для дебага."""
import os
import time
import tempfile

from fastapi import File, Form, HTTPException, UploadFile
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pipeline import DEEPSEEK_MODEL, generate_quiz, process_document


def parse_pages(spec: str) -> list:
    """«1-10», «1,3,5», «1-3,7» → [1,2,…]. Пусто → None (авто)."""
    spec = (spec or "").strip()
    if not spec:
        return None
    pages: set = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            try:
                a, b = part.split("-", 1)
                pages.update(range(int(a), int(b) + 1))
            except ValueError:
                continue
        elif part.isdigit():
            pages.add(int(part))
    return sorted(p for p in pages if p >= 1) or None


app = FastAPI(title="Teacher Quiz Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": DEEPSEEK_MODEL}


@app.post("/quiz")
async def quiz(
    text: str = Form(""),
    file: UploadFile = File(None),
    pages: str = Form(""),
    topic: str = Form(""),
    num_questions: int = Form(5),
) -> dict:
    """Единая точка генерации квиза. Если приложен файл — квиз по документу
    (с учётом страниц/темы), иначе — по вставленному тексту."""
    num = max(1, min(int(num_questions), 10))
    topic_clean = topic.strip() or None
    t0 = time.perf_counter()

    # Режим «документ»
    if file is not None and file.filename:
        page_range = parse_pages(pages)
        suffix = os.path.splitext(file.filename)[1] or ".txt"
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await file.read())
                tmp_path = tmp.name

            result = process_document(tmp_path, num_questions=num, page_range=page_range, topic=topic_clean)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)

            if not result.get("quiz"):
                raise HTTPException(status_code=502, detail="Не удалось сгенерировать квиз (пустой текст/страницы или ошибка DeepSeek)")

            return {
                "quiz": result["quiz"],
                "meta": {
                    "model": DEEPSEEK_MODEL,
                    "source": "document",
                    "filename": file.filename,
                    "pages": pages or "все/авто",
                    "topic": topic or "—",
                    "words": result.get("words"),
                    "generated": len(result["quiz"]),
                    "connectivity": result.get("connectivity"),
                    "elapsed_ms": elapsed_ms,
                },
            }
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # Режим «текст»
    if text and text.strip():
        result = generate_quiz(text, num, topic_clean)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        if not result:
            raise HTTPException(status_code=502, detail="DeepSeek не вернул квиз (проверьте ключ/баланс)")
        return {
            "quiz": result,
            "meta": {
                "model": DEEPSEEK_MODEL,
                "source": "text",
                "topic": topic or "—",
                "input_chars": len(text),
                "generated": len(result),
                "elapsed_ms": elapsed_ms,
            },
        }

    raise HTTPException(status_code=400, detail="Вставьте текст или выберите файл")
