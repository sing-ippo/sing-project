"""Веб-API генератора квизов для преподавателей (без Telegram).
Браузер шлёт текст или файл → DeepSeek генерит квиз → отдаём JSON."""
import os
import tempfile

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from pipeline import generate_quiz, process_document

app = FastAPI(title="Teacher Quiz Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/quiz")
async def quiz(text: str = Body(..., embed=True), num_questions: int = Body(5, embed=True)) -> dict:
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Пустой текст")
    num = max(1, min(int(num_questions), 10))
    result = generate_quiz(text, num)
    if not result:
        raise HTTPException(status_code=502, detail="Не удалось сгенерировать квиз (проверьте ключ DeepSeek)")
    return {"quiz": result}


@app.post("/quiz_file")
async def quiz_file(file: UploadFile = File(...)) -> dict:
    suffix = os.path.splitext(file.filename or "doc.txt")[1] or ".txt"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name
        result = process_document(tmp_path, num_questions=5)
        if not result.get("quiz"):
            raise HTTPException(status_code=502, detail="Не удалось сгенерировать квиз из файла")
        return {"quiz": result["quiz"]}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
