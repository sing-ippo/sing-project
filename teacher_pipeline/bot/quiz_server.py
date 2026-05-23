"""Веб-API генератора квизов для преподавателей (без Telegram).
Браузер шлёт текст или файл → DeepSeek генерит квиз → отдаём JSON + meta для дебага."""
import os
import time
import tempfile

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from pipeline import DEEPSEEK_MODEL, chunk_text, generate_quiz, load_document, process_document


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
async def quiz(text: str = Body(..., embed=True), num_questions: int = Body(5, embed=True)) -> dict:
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Пустой текст")
    num = max(1, min(int(num_questions), 10))

    t0 = time.perf_counter()
    result = generate_quiz(text, num)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    if not result:
        raise HTTPException(status_code=502, detail="DeepSeek не вернул квиз (проверьте ключ/баланс)")

    return {
        "quiz": result,
        "meta": {
            "model": DEEPSEEK_MODEL,
            "source": "text",
            "input_chars": len(text),
            "requested": num,
            "generated": len(result),
            "elapsed_ms": elapsed_ms,
        },
    }


@app.post("/quiz_file")
async def quiz_file(file: UploadFile = File(...)) -> dict:
    suffix = os.path.splitext(file.filename or "doc.txt")[1] or ".txt"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        t0 = time.perf_counter()
        text = load_document(tmp_path)
        if not text:
            raise HTTPException(status_code=400, detail="Файл пустой, слишком большой (>50KB) или формат не поддержан")
        chunks = chunk_text(text)
        combined = "".join(f"[ID:{c['id']}]\n{c['text']}\n\n" for c in chunks)
        result = generate_quiz(combined, 5)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if not result:
            raise HTTPException(status_code=502, detail="DeepSeek не вернул квиз из файла")

        return {
            "quiz": result,
            "meta": {
                "model": DEEPSEEK_MODEL,
                "source": "file",
                "filename": file.filename,
                "input_chars": len(text),
                "chunks": len(chunks),
                "generated": len(result),
                "elapsed_ms": elapsed_ms,
            },
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/quiz_doc")
async def quiz_doc(
    file: UploadFile = File(...),
    pages: str = Form(""),
    topic: str = Form(""),
    num_questions: int = Form(5),
) -> dict:
    """Квиз по документу/учебнику: выбор страниц (PDF) и/или темы."""
    num = max(1, min(int(num_questions), 10))
    page_range = parse_pages(pages)
    suffix = os.path.splitext(file.filename or "doc.txt")[1] or ".txt"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        t0 = time.perf_counter()
        result = process_document(tmp_path, num_questions=num, page_range=page_range, topic=(topic.strip() or None))
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
                "elapsed_ms": elapsed_ms,
            },
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
