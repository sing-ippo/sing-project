"""Грунтинг ответов: поиск по mirea.ru + формулировка ответа через DeepSeek.

Используется в voice_server.py как RAG-комбо: на каждый вопрос собираем контекст
(записи FAQ + сниппеты с mirea.ru) и просим DeepSeek сформулировать короткий ответ.
"""
import os
import re

import httpx
from bs4 import BeautifulSoup

# Стоп-слова: вопросительные, предлоги, местоимения. Поиск mirea.ru — фразовый
# (AND по словам), поэтому из вопроса берём только содержательные слова.
_STOPWORDS = {
    "как", "что", "где", "когда", "почему", "зачем", "какой", "какая", "какие",
    "какую", "каком", "чём", "чем", "кто", "куда", "откуда", "сколько",
    "можно", "нужно", "надо", "это", "этот", "эта", "эти", "для", "при", "про",
    "что-бы", "чтобы", "или", "есть", "быть", "мне", "нам", "вам", "наш", "мой",
    "или", "ну", "вот", "там", "тут", "ещё", "уже", "очень", "такое", "такой",
    "ли", "же", "бы", "не", "на", "по", "из", "от", "до", "об", "под", "над",
    "так", "тоже", "также", "если", "то", "вообще", "типа",
    # частые глаголы-действия: для поиска по сайту важны существительные/акронимы
    "зайти", "войти", "попасть", "узнать", "получить", "сделать", "найти",
    "посмотреть", "оформить", "взять", "сдать", "подать", "связаться",
    "добраться", "делать", "пройти", "сдавать", "закрыть", "восстановиться",
    "перевестись", "поступить", "поесть",
}
_WORD_RE = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)


def _keywords(question: str) -> list[str]:
    """Содержательные слова вопроса (len>=3, без стоп-слов), порядок сохранён."""
    seen: set[str] = set()
    result: list[str] = []
    for word in _WORD_RE.findall(question.lower()):
        if len(word) >= 3 and word not in _STOPWORDS and word not in seen:
            seen.add(word)
            result.append(word)
    return result

MIREA_SEARCH_URL = "https://www.mirea.ru/search/"
MIREA_BASE = "https://www.mirea.ru"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

_USER_AGENT = "Mozilla/5.0 (compatible; MireaKiosk/1.0)"

SYSTEM_PROMPT = (
    "Ты — голосовой ассистент РТУ МИРЭА для абитуриентов и студентов. "
    "Отвечай кратко (1–3 предложения), простым разговорным языком, пригодным для озвучки. "
    "В приоритете — факты из блока «БАЗА ЗНАНИЙ» (это выверенные ответы вуза), "
    "дополняй их выдержками из блока «С САЙТА mirea.ru». "
    "Если в контексте есть конкретный адрес сайта, ссылка, телефон или почта, "
    "относящиеся к ответу — обязательно назови их (адреса диктуй как «online-edu точка mirea точка ru»). "
    "НЕ выдумывай адреса, даты, цифры и факты, которых нет в предоставленном контексте. "
    "Если точного ответа в контексте нет — честно скажи об этом и предложи "
    "уточнить на сайте mirea.ru или в приёмной комиссии."
)


def _parse_results(html: str, top_n: int) -> list[dict]:
    results: list[dict] = []
    soup = BeautifulSoup(html, "html.parser")
    for item in soup.select(".search-item")[:top_n]:
        link = item.find("a")
        preview = item.select_one(".search-preview")
        if not link:
            continue
        href = link.get("href", "")
        url = href if href.startswith("http") else MIREA_BASE + href
        results.append({
            "title": link.get_text(strip=True),
            "url": url,
            "snippet": preview.get_text(" ", strip=True) if preview else "",
        })
    return results


async def search_mirea(question: str, top_n: int = 5) -> list[dict]:
    """Ищет по встроенному поиску mirea.ru. Возвращает [{title, url, snippet}].
    Поиск фразовый (AND), поэтому пробуем по убыванию специфичности:
    все ключевые слова → топ-2 самых длинных по отдельности. При любой ошибке → []."""
    keywords = _keywords(question)
    if not keywords:
        keywords = [question.strip()]

    # Стратегии запроса: вся фраза ключевых слов, затем отдельные длинные слова
    by_length = sorted(keywords, key=len, reverse=True)
    queries: list[str] = []
    for q in [" ".join(keywords), *by_length[:2]]:
        if q and q not in queries:
            queries.append(q)

    try:
        async with httpx.AsyncClient(timeout=4.0, headers={"User-Agent": _USER_AGENT}) as client:
            for query in queries:
                response = await client.get(MIREA_SEARCH_URL, params={"q": query})
                response.raise_for_status()
                results = _parse_results(response.text, top_n)
                if results:
                    return results
    except Exception:
        return []
    return []


def _build_context(faq_candidates: list[dict], snippets: list[dict]) -> str:
    parts: list[str] = []
    if faq_candidates:
        parts.append("БАЗА ЗНАНИЙ:")
        for c in faq_candidates:
            parts.append(f"- В: {c.get('question','')}\n  О: {c.get('answer','')}")
    if snippets:
        parts.append("\nС САЙТА mirea.ru:")
        for s in snippets:
            parts.append(f"- {s.get('title','')}: {s.get('snippet','')} ({s.get('url','')})")
    if not parts:
        parts.append("(контекст пуст)")
    return "\n".join(parts)


async def ask_deepseek(question: str, faq_candidates: list[dict], snippets: list[dict]) -> str | None:
    """Просит DeepSeek сформулировать ответ из контекста. None — если нет ключа или ошибка."""
    if not DEEPSEEK_API_KEY:
        return None

    user_message = (
        f"Вопрос: {question}\n\n"
        f"{_build_context(faq_candidates, snippets)}"
    )
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(DEEPSEEK_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        answer = data["choices"][0]["message"]["content"].strip()
        return answer or None
    except Exception:
        return None
