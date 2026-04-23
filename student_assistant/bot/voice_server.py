import base64
import io
import os
import subprocess
import tempfile
from pathlib import Path

# Voice server Артема

import numpy as np
import scipy.io.wavfile as wavfile
import torch
import whisper
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from search_engine import get_best_answer, load_faq_from_file


BASE_DIR = Path(__file__).resolve().parent
FAQ_PATH = BASE_DIR / "faq.json"

WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
TTS_LANGUAGE = "ru"
TTS_SPEAKER_MODEL = "v3_1_ru"
TTS_VOICE = "aidar"
TTS_SAMPLE_RATE = 48000

app = FastAPI(title="Student Assistant Voice Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

whisper_model = None
tts_model = None
faq_data = None


def webm_to_wav(input_path: str) -> str:
    output_path = str(Path(input_path).with_suffix(".wav"))
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, output_path],
        check=True,
        capture_output=True,
    )
    return output_path


def tensor_to_wav_bytes(audio_tensor: torch.Tensor, sample_rate: int = TTS_SAMPLE_RATE) -> bytes:
    audio_np = audio_tensor.cpu().numpy()

    if audio_np.ndim > 1:
        audio_np = np.squeeze(audio_np)

    audio_np = np.clip(audio_np, -1.0, 1.0)
    audio_int16 = (audio_np * 32767).astype(np.int16)

    buffer = io.BytesIO()
    wavfile.write(buffer, sample_rate, audio_int16)
    return buffer.getvalue()


def synthesize_answer(answer: str) -> bytes:
    audio_tensor = tts_model.apply_tts(
        text=answer,
        speaker=TTS_VOICE,
        sample_rate=TTS_SAMPLE_RATE,
    )
    return tensor_to_wav_bytes(audio_tensor, TTS_SAMPLE_RATE)


def transcribe_audio(wav_path: str) -> str:
    result = whisper_model.transcribe(wav_path, language="ru")
    return result.get("text", "").strip()


@app.on_event("startup")
async def startup_event() -> None:
    global whisper_model, tts_model, faq_data

    if not FAQ_PATH.exists():
        raise RuntimeError(f"Файл FAQ не найден: {FAQ_PATH}")

    faq_data = load_faq_from_file(FAQ_PATH)
    whisper_model = whisper.load_model(WHISPER_MODEL_NAME)

    tts_model, _ = torch.hub.load(
        repo_or_dir="snakers4/silero-models",
        model="silero_tts",
        language=TTS_LANGUAGE,
        speaker=TTS_SPEAKER_MODEL,
    )

    if hasattr(tts_model, "to"):
        tts_model.to("cpu")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/ask")
async def ask(file: UploadFile = File(...)) -> dict:
    allowed_content_types = {
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/webm",
        "video/webm",
        "application/octet-stream",
    }

    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются только wav и webm файлы",
        )

    suffix = Path(file.filename or "audio.webm").suffix.lower()
    if suffix not in {".wav", ".webm"}:
        if file.content_type in {"audio/webm", "video/webm"}:
            suffix = ".webm"
        else:
            suffix = ".wav"

    temp_input_path = None
    temp_wav_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_input_path = temp_file.name
            temp_file.write(await file.read())

        if suffix == ".webm":
            temp_wav_path = webm_to_wav(temp_input_path)
        else:
            temp_wav_path = temp_input_path

        question = transcribe_audio(temp_wav_path)
        if not question:
            raise HTTPException(status_code=400, detail="Не удалось распознать вопрос")

        faq_result = await get_best_answer(question, faq_data)
        answer = faq_result["answer"]

        audio_bytes = synthesize_answer(answer)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return {
            "question": question,
            "answer": answer,
            "audio_base64": audio_base64,
        }

    except subprocess.CalledProcessError as error:
        stderr = error.stderr.decode("utf-8", errors="ignore") if error.stderr else ""
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка ffmpeg при конвертации аудио: {stderr}",
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {error}")
    finally:
        for path in {temp_input_path, temp_wav_path}:
            if path and Path(path).exists():
                try:
                    Path(path).unlink()
                except OSError:
                    pass