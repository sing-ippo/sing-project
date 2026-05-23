"""Веб-API генератора квизов для преподавателей (без Telegram).
Браузер шлёт текст или файл → DeepSeek генерит квиз → отдаём JSON + meta для дебага."""
import os
import time
import tempfile

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from pipeline import DEEPSEEK_MODEL, chunk_text, generate_quiz, load_document

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
