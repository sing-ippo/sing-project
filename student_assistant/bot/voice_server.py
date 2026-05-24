import base64
import io
import json
import os
import re
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile
import torch
import whisper
from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from search_engine import (
    DEFAULT_FALLBACK_ANSWER,
    load_faq_from_file,
    search,
    split_words,
)
from web_fallback import DEEPSEEK_API_KEY, _STOPWORDS, ask_deepseek, search_mirea

from pymorphy3 import MorphAnalyzer

_morph = MorphAnalyzer()
_word_re = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)


def lemmatize(text: str) -> str:
    """Приводит слова к нормальной форме — ключевые слова FAQ тоже лемматизированы,
    поэтому «общежитии» начинает совпадать с «общежитие»."""
    return " ".join(_morph.parse(w)[0].normal_form for w in _word_re.findall(text.lower()))


BASE_DIR = Path(__file__).resolve().parent
# Единый источник FAQ — выход пайплайна data/faq.json (можно переопределить env FAQ_PATH)
FAQ_PATH = Path(os.getenv("FAQ_PATH", str(BASE_DIR.parent / "data" / "faq.json")))
REQUESTS_LOG = Path(os.getenv("REQUESTS_LOG", str(BASE_DIR / "requests.jsonl")))

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


_DOMAIN_RE = re.compile(r"[a-zA-Z0-9]+(?:[.\-][a-zA-Z0-9]+)+")


def make_speakable(text: str) -> str:
    """Готовит текст к озвучке: в доменах/ссылках «.» → « точка », «-» → « дефис ».
    Применяется ТОЛЬКО к синтезу речи; на экран идёт исходный текст с чистым URL."""
    def repl(match: re.Match) -> str:
        return match.group(0).replace(".", " точка ").replace("-", " дефис ")
    return _DOMAIN_RE.sub(repl, text)


def synthesize_answer(answer: str) -> bytes:
    audio_tensor = tts_model.apply_tts(
        text=make_speakable(answer),
        speaker=TTS_VOICE,
        sample_rate=TTS_SAMPLE_RATE,
    )
    return tensor_to_wav_bytes(audio_tensor, TTS_SAMPLE_RATE)


WHISPER_PROMPT = (
    "Вопрос студента или абитуриента РТУ МИРЭА. Термины: СДО, ЛКС, личный кабинет, "
    "ВУЦ, деканат, БРС, пересдача, стипендия, общежитие, бакалавриат, магистратура, "
    "ЕГЭ, приёмная комиссия, День открытых дверей."
)


def transcribe_audio(wav_path: str) -> str:
    result = whisper_model.transcribe(wav_path, language="ru", initial_prompt=WHISPER_PROMPT)
    return result.get("text", "").strip()


def has_exact_word_match(question: str, entry: dict) -> bool:
    """True, если хотя бы одно слово вопроса целиком совпадает со словом
    из keywords или текста вопроса FAQ-записи. Отсекает ложные срабатывания
    поиска на бессмысленных запросах (которые матчатся лишь по префиксам)."""
    question_words = split_words(question)
    entry_words: set[str] = split_words(entry.get("question", ""))
    for keyword in entry.get("keywords", []):
        entry_words |= split_words(keyword)
    return bool(question_words & entry_words)


def log_request(request_id: str, query: str, answer: str, matched: bool, source: str = "none") -> None:
    """Пишет запрос в requests.jsonl в формате, который понимает дашборд аналитики.
    source — кто ответил: deepseek / faq-offline / none.
    helpful=None пока пользователь не нажал «Помогло?» (обновляется в /feedback)."""
    record = {
        "request_id": request_id,
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "answer": answer,
        "matched": matched,
        "helpful": None,
        "source": source,
    }
    try:
        with REQUESTS_LOG.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def set_feedback(request_id: str, helpful: bool) -> bool:
    """Проставляет helpful у записи requests.jsonl по request_id. Перезапись файла
    (для киоска объём мал). True — если запись найдена и обновлена."""
    if not REQUESTS_LOG.exists():
        return False
    found = False
    lines: list[str] = []
    try:
        with REQUESTS_LOG.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("request_id") == request_id:
                    rec["helpful"] = helpful
                    found = True
                lines.append(json.dumps(rec, ensure_ascii=False))
        if found:
            with REQUESTS_LOG.open("w", encoding="utf-8") as file:
                file.write("\n".join(lines) + "\n")
    except (OSError, json.JSONDecodeError):
        return False
    return found


@app.on_event("startup")
async def startup_event() -> None:
    global whisper_model, tts_model, faq_data

    if not FAQ_PATH.exists():
        raise RuntimeError(f"Файл FAQ не найден: {FAQ_PATH}")

    faq_data = load_faq_from_file(FAQ_PATH)
    whisper_model = whisper.load_model(WHISPER_MODEL_NAME)

    # Обход бага torch.hub: _validate_not_a_forked_repo падает с
    # KeyError: 'Authorization', когда не задан GITHUB_TOKEN.
    if hasattr(torch.hub, "_validate_not_a_forked_repo"):
        torch.hub._validate_not_a_forked_repo = lambda *args, **kwargs: True

    tts_model, _ = torch.hub.load(
        repo_or_dir="snakers4/silero-models",
        model="silero_tts",
        language=TTS_LANGUAGE,
        speaker=TTS_SPEAKER_MODEL,
        trust_repo=True,  # без этого torch.hub просит подтверждение через input() → EOFError в контейнере
    )

    if hasattr(tts_model, "to"):
        tts_model.to("cpu")


# URL: полные ссылки или «голые» домены. Lookbehind (?<![@\w.]) бережёт email (pk@mirea.ru).
_URL_RE = re.compile(
    r"https?://[^\s)]+|(?<![@\w.])(?:[a-z0-9-]+\.)+(?:ru|рф|com|org)(?:/[^\s)]*)?",
    re.IGNORECASE,
)
# Низкокачественные/новостные пути — их в карточки не пускаем
_JUNK_PATHS = ("/news/", "/press", "/announc", "/search")
# Голый корень главного сайта — не «полезная ссылка» (а вот online-edu.mirea.ru и т.п. — да)
_GENERIC_URLS = {"mirea.ru", "www.mirea.ru"}
# Леммы названия вуза/общих слов — они есть на каждой странице, по ним нельзя судить о релевантности
_GENERIC_TERMS = {"мирэа", "ртэ", "мирэ", "университет", "вуз", "mirea", "rtu"}


def _extract_urls(text: str) -> list[str]:
    """Достаёт ссылки из текста ответа, нормализует: добавляет схему, срезает хвост."""
    urls: list[str] = []
    for raw in _URL_RE.findall(text or ""):
        url = raw.rstrip(".,);:")
        if not url.startswith("http"):
            url = "https://" + url
        urls.append(url)
    return urls


def _norm_url(url: str) -> str:
    """Ключ для дедупа: без схемы, без хвостового слэша, в нижнем регистре."""
    return re.sub(r"^https?://", "", url.lower()).rstrip("/")


def build_sources(lemmatized: str, faq_candidates: list[dict], snippets: list[dict]) -> list[dict]:
    """«Полезные ссылки»: сперва канон из совпавших FAQ-ответов, иначе —
    строго отфильтрованный веб (без новостей, с совпадением слов). Пусто — если нечего показать."""
    sources: list[dict] = []
    seen: set[str] = set()

    # 1) Канон из FAQ — только для кандидатов, реально совпавших с вопросом
    for cand in faq_candidates[:3]:
        entry = next((e for e in faq_data if e.get("id") == cand.get("id")), None)
        if not (entry and has_exact_word_match(lemmatized, entry)):
            continue
        # первый «полезный» URL ответа (не голый корень mirea.ru, не дубль)
        url = next((u for u in _extract_urls(cand.get("answer", ""))
                    if _norm_url(u) not in _GENERIC_URLS and _norm_url(u) not in seen), None)
        if not url:
            continue
        seen.add(_norm_url(url))
        answer_text = cand.get("answer", "")
        sources.append({
            "title": cand.get("question", ""),
            "url": url,
            "snippet": answer_text[:130] + ("…" if len(answer_text) > 130 else ""),
        })
        if len(sources) >= 3:
            return sources

    if sources:
        return sources

    # 2) Фолбэк — отфильтрованный поиск mirea.ru (только если из базы ничего не вышло).
    # Совпадение считаем по СОДЕРЖАТЕЛЬНЫМ словам: название вуза («мирэа») есть везде,
    # по нему судить о релевантности нельзя.
    content_lemmas = {
        t for t in lemmatized.split()
        if len(t) >= 3 and t not in _GENERIC_TERMS and t not in _STOPWORDS
    }
    if not content_lemmas:
        return sources
    # Сколько содержательных слов вопроса должно встретиться в сниппете. Если в вопросе
    # 2+ значимых слова — требуем хотя бы два: одно случайное совпадение (полисемия,
    # напр. «канал» связи в диссертации) не делает ссылку релевантной.
    need = 2 if len(content_lemmas) >= 2 else 1
    for s in snippets:
        url = s.get("url", "")
        if any(p in url.lower() for p in _JUNK_PATHS):
            continue
        text_lemmas = set(lemmatize(f"{s.get('title', '')} {s.get('snippet', '')}").split())
        if len(content_lemmas & text_lemmas) < need:
            continue
        key = _norm_url(url)
        if not url or key in seen or key in _GENERIC_URLS:
            continue
        seen.add(key)
        sources.append({"title": s.get("title", ""), "url": url, "snippet": s.get("snippet", "")})
        if len(sources) >= 3:
            break
    return sources


async def answer_question(question: str, history: list[dict] | None = None) -> dict:
    """Единый движок ответа: релевантные FAQ + сниппеты mirea.ru → DeepSeek.
    При недоступности LLM — деградация на чистый FAQ с гейтом точного совпадения.
    history — прошлые ходы диалога [{role, content}] для кореференции (только для генерации;
    ретрив идёт по текущему вопросу). Возвращает {answer, source, sources}; STT/TTS — см. /ask."""
    lemmatized = lemmatize(question)
    faq_candidates = await search(lemmatized, faq_data, top_n=5)
    snippets = await search_mirea(question)

    answer = None
    source = "none"
    if DEEPSEEK_API_KEY:
        answer = await ask_deepseek(question, faq_candidates, snippets, history=history)
        if answer:
            source = "deepseek"

    if not answer:
        if faq_candidates:
            entry = next((e for e in faq_data if e.get("id") == faq_candidates[0]["id"]), None)
            if entry and has_exact_word_match(lemmatized, entry):
                answer = faq_candidates[0]["answer"]
                source = "faq-offline"
        if not answer:
            answer = DEFAULT_FALLBACK_ANSWER

    sources = build_sources(lemmatized, faq_candidates, snippets)
    return {"answer": answer, "source": source, "sources": sources}


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

        result = await answer_question(question)
        answer = result["answer"]
        source = result["source"]

        request_id = uuid.uuid4().hex
        log_request(request_id, question, answer, matched=(source != "none"), source=source)

        audio_bytes = synthesize_answer(answer)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return {
            "request_id": request_id,
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


def _clean_history(raw: list) -> list[dict]:
    """Готовит историю диалога от клиента к передаче в LLM: только роли user/assistant,
    непустой текстовый content (обрезан), последние 6 ходов — защита от раздувания промпта."""
    cleaned: list[dict] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            cleaned.append({"role": role, "content": content.strip()[:800]})
    return cleaned[-6:]


@app.post("/ask_text")
async def ask_text(question: str = Body(..., embed=True), history: list = Body(default=[], embed=True)) -> dict:
    """Текстовая альтернатива /ask: вопрос строкой → ответ строкой (без речи).
    history — прошлые ходы диалога для кореференции follow-up-вопросов.
    Тот же движок answer_question; ответ с реальными URL (без make_speakable)."""
    question = (question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Пустой вопрос")

    result = await answer_question(question, history=_clean_history(history))
    answer = result["answer"]
    source = result["source"]

    request_id = uuid.uuid4().hex
    log_request(request_id, question, answer, matched=(source != "none"), source=source)

    return {
        "request_id": request_id,
        "question": question,
        "answer": answer,
        "source": source,
        "sources": result.get("sources", []),
    }


@app.post("/feedback")
async def feedback(request_id: str = Body(..., embed=True), helpful: bool = Body(..., embed=True)) -> dict:
    """Отмечает, помог ли ответ. Обновляет helpful у записи requests.jsonl."""
    updated = set_feedback(request_id, helpful)
    return {"ok": updated}
