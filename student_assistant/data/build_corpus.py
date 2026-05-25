"""Сборка семантического индекса (corpus.npz) для RAG-ассистента.

Берёт курируемый список официальных страниц mirea.ru + записи faq.json,
извлекает текст, режет на чанки, считает эмбеддинги и сохраняет индекс.
Запуск офлайн (нужен интернет для фетча страниц и загрузки модели):
    python build_corpus.py
Неудачные/недоступные URL просто пропускаются — в индекс попадает только
реально скачанное, поэтому ссылки в индексе самопроверяемые.
"""
import json
import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# rag.py лежит в соседнем каталоге bot/
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent / "bot"))
import rag  # noqa: E402

from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402

FAQ_PATH = BASE_DIR / "faq.json"
OUTPUT = BASE_DIR / "corpus.npz"
USER_AGENT = "Mozilla/5.0 (compatible; MireaKiosk/1.0)"
_URL_RE = re.compile(r"https?://[^\s)]+|(?<![@\w.])(?:[a-z0-9-]+\.)+(?:ru|рф|com|org)(?:/[^\s)]*)?", re.IGNORECASE)

# --- Официальные RuTube-каналы РТУ МИРЭА: приёмная, основной, ЦДО, центр карьеры ---
RUTUBE_CHANNELS = [23722201, 23657936, 23657593, 30150318]
MAX_VIDEOS_PER_CHANNEL = 150
RUTUBE_API = "https://rutube.ru/api/video/person/{cid}/?page={page}"

# --- Курируемый список официальных страниц. Команда поддерживает его. ---
# Недоступные/пустые отсеются автоматически при сборке.
SEED_URLS = [
    "https://www.mirea.ru/education/",
    "https://www.mirea.ru/sveden/",
    "https://www.mirea.ru/sveden/grants/",          # стипендии и меры поддержки
    "https://www.mirea.ru/schedule/",
    "https://online-edu.mirea.ru/",
    # priem.mirea.ru и /students/ стабильно валятся по TLS-таймауту из контейнера — исключены.
]


def fetch_text(url: str) -> tuple[str, str]:
    """(title, plain_text) основного контента страницы. Пусто — если не удалось.
    Три попытки с увеличенным таймаутом — некоторые домены (priem) медленно отдают TLS."""
    resp = None
    for attempt in range(3):
        try:
            resp = httpx.get(url, timeout=30.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
            resp.raise_for_status()
            break
        except Exception as e:
            if attempt == 2:
                print(f"  ПРОПУСК {url}: {e}")
                return "", ""
            print(f"  повтор {url} (попытка {attempt + 2})…")
    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else url
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript", "form"]):
        tag.decompose()
    main = soup.find("main") or soup.find(id="content") or soup.body or soup
    text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))
    return title, text


def fetch_rutube_videos() -> list[dict]:
    """Тянет ролики официальных каналов через публичный JSON-API RuTube.
    Возвращает [{tag:'video', title, url(embed), text, thumb}]. Ошибки канала — пропускаем."""
    videos: list[dict] = []
    for cid in RUTUBE_CHANNELS:
        got = 0
        page = 1
        while got < MAX_VIDEOS_PER_CHANNEL:
            try:
                resp = httpx.get(RUTUBE_API.format(cid=cid, page=page), timeout=15.0,
                                 headers={"User-Agent": USER_AGENT})
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"  RuTube {cid} стр.{page}: пропуск ({e})")
                break
            results = data.get("results", [])
            if not results:
                break
            for v in results:
                if v.get("is_deleted") or v.get("is_hidden"):
                    continue
                title = (v.get("title") or "").strip()
                embed = (v.get("embed_url") or "").strip()
                if not title or not embed.startswith("https://rutube.ru/"):
                    continue
                desc = (v.get("description") or "").strip()
                videos.append({
                    "tag": "video",
                    "title": title,
                    "url": embed,
                    "text": f"{title}. {desc}".strip(),
                    "thumb": v.get("thumbnail_url") or "",
                    "duration": int(v.get("duration") or 0),
                })
                got += 1
                if got >= MAX_VIDEOS_PER_CHANNEL:
                    break
            if not data.get("next"):
                break
            page += 1
        print(f"  RuTube канал {cid}: видео {got}")
    return videos


def faq_url(answer: str) -> str:
    for raw in _URL_RE.findall(answer or ""):
        url = raw.rstrip(".,);:")
        return url if url.startswith("http") else "https://" + url
    return ""


def main() -> None:
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    meta: list[dict] = []
    texts: list[str] = []

    # 1) Официальные страницы
    print("Страницы:")
    for url in SEED_URLS:
        title, text = fetch_text(url)
        if len(text) < 200:
            if text:
                print(f"  ПРОПУСК {url}: мало текста ({len(text)})")
            continue
        chunks = splitter.split_text(text)
        for ch in chunks:
            if len(ch.strip()) < 80:
                continue
            meta.append({"tag": "page", "title": title, "url": url, "text": ch})
            texts.append(ch)
        print(f"  OK {url}: чанков {len(chunks)}")

    # 2) FAQ-записи (для семантического матча базы)
    if FAQ_PATH.exists():
        faq = json.loads(FAQ_PATH.read_text(encoding="utf-8"))
        for e in faq:
            q, a = e.get("question", ""), e.get("answer", "")
            if not a:
                continue
            meta.append({"tag": "faq", "title": q, "url": faq_url(a), "text": f"{q}\n{a}"})
            texts.append(f"{q} {a}")
        print(f"FAQ: записей {len(faq)}")

    # 3) Видео с официальных каналов RuTube
    print("RuTube:")
    for v in fetch_rutube_videos():
        meta.append({"tag": "video", "title": v["title"], "url": v["url"], "text": v["text"],
                     "thumb": v["thumb"], "duration": v["duration"]})
        texts.append(v["text"])

    if not texts:
        print("ОШИБКА: пусто, индекс не собран.")
        sys.exit(1)

    print(f"Эмбеддинги: {len(texts)} фрагментов, модель {rag.EMBEDDING_MODEL}…")
    vectors = rag.embed_passages(texts)
    rag.save_corpus(str(OUTPUT), vectors, meta)
    by_tag = {}
    for m in meta:
        by_tag[m["tag"]] = by_tag.get(m["tag"], 0) + 1
    print(f"Готово: {OUTPUT} | всего {len(meta)} {by_tag}, dim={vectors.shape[1]}")


if __name__ == "__main__":
    main()
