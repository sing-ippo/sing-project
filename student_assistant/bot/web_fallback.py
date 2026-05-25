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
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

_USER_AGENT = "Mozilla/5.0 (compatible; MireaKiosk/1.0)"

# Тон речи ассистента — настраивается без правки кода через env ASSISTANT_TONE.
ASSISTANT_TONE = os.getenv(
    "ASSISTANT_TONE",
    "Тон дружелюбный и ясный. Подстраивай обращение под собеседника: на «ты» с абитуриентами и "
    "студентами, на «вы» с родителями и преподавателями (по умолчанию — вежливо-нейтрально). "
    "О себе говори в мужском роде («рад помочь»), последовательно.",
)

SYSTEM_PROMPT = (
    "Ты — ассистент РТУ МИРЭА. Помогаешь всем: абитуриентам, студентам, их родителям, преподавателям "
    "и гостям. " + ASSISTANT_TONE + " "
    "Общайся естественно: здоровайся, поддерживай короткий small-talk, помни и используй сказанное "
    "в этом диалоге (имя, кто пользователь). "
    "\n\n"
    "ПОЙМИ, КТО ПЕРЕД ТОБОЙ. Если для уместного ответа важно, кто спрашивает (например, про поступление "
    "родитель и абитуриент спрашивают с разным акцентом), а из диалога это не ясно — вежливо уточни "
    "один раз: абитуриент, студент, родитель или преподаватель. Запомни и подстрой тон и детализацию. "
    "\n\n"
    "ФАКТЫ О ВУЗЕ (контакты, адреса, телефоны, даты, суммы, правила приёма, конкретные сервисы и ссылки) "
    "приводи ТОЛЬКО из блоков «БАЗА ЗНАНИЙ» и «ОФИЦИАЛЬНЫЕ СТРАНИЦЫ» (приоритет — «БАЗА ЗНАНИЙ»). "
    "НЕ выдумывай URL, сервисы, даты и цифры. Если такого факта нет в контексте — честно скажи и "
    "предложи уточнить на mirea.ru или в приёмной комиссии. Не обещай того, чего не умеешь (искать "
    "расписание конкретной группы, заходить в личные кабинеты, знать аудитории/время пар) и не "
    "добавляй непрошеных «успокаивающих» деталей, которых нет в контексте. По справочным вопросам "
    "отвечай коротко (1–3 предложения). "
    "\n\n"
    "УЧЕБНЫЕ МАТЕРИАЛЫ. Если просят объяснить тему, разобрать задачу, дать конспект или пример по "
    "предмету (математика, физика, программирование и т.п.) — это НЕ факт о вузе, и ты можешь "
    "объяснять из своих знаний. Дай понятный структурированный ответ (markdown: заголовки, списки), "
    "формулы выводи в LaTeX: строчные в `$...$`, выключные в `$$...$$`. Тут можно подробнее, чем по "
    "справочным вопросам. Если тема сложная или возможны нюансы — посоветуй свериться с учебником "
    "или преподавателем. "
    "\n\n"
    "На приветствия, благодарности и личное из разговора отвечай сам по ходу беседы, НЕ отправляй на сайт."
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
            "title": link.get_text(" ", strip=True),
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


def _build_context(hits: list[dict]) -> str:
    """Контекст для LLM из семантических хитов: FAQ-записи → «БАЗА ЗНАНИЙ»,
    страницы → «ОФИЦИАЛЬНЫЕ СТРАНИЦЫ» (с их URL — они выверены сборкой индекса)."""
    faq = [h for h in hits if h.get("tag") == "faq"]
    pages = [h for h in hits if h.get("tag") == "page"]
    parts: list[str] = []
    if faq:
        parts.append("БАЗА ЗНАНИЙ (выверенные ответы вуза):")
        for h in faq:
            parts.append(f"- {h.get('text', '')}")
    if pages:
        parts.append("\nОФИЦИАЛЬНЫЕ СТРАНИЦЫ mirea.ru:")
        for h in pages:
            parts.append(f"- {h.get('title', '')}: {h.get('text', '')} ({h.get('url', '')})")
    if not parts:
        parts.append("(контекст пуст)")
    return "\n".join(parts)


async def ask_deepseek(
    question: str,
    hits: list[dict],
    history: list[dict] | None = None,
) -> str | None:
    """Просит DeepSeek сформулировать ответ из семантического контекста (hits).
    None — если нет ключа или ошибка. history — прошлые ходы диалога для кореференции."""
    if not DEEPSEEK_API_KEY:
        return None

    user_message = (
        f"Вопрос: {question}\n\n"
        f"{_build_context(hits)}"
    )
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": user_message})
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.2,
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


# --- Подготовка поискового запроса (rewrite + словарь алиасов) ---
# Сленг/сокращения → формальные термины вуза. Команда пополняет.
ALIASES = {
    "повышка": "повышенная стипендия",
    "общага": "общежитие",
    "академ": "академический отпуск",
    "матпомощь": "материальная помощь",
    "стипуха": "стипендия",
    "зачётка": "зачётная книжка",
    "лк": "личный кабинет",
    "пересдача": "пересдача экзамена",
    "автомат": "автоматический зачёт",
    "доды": "дни открытых дверей",
    "дод": "день открытых дверей",
}
_ALIAS_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in ALIASES) + r")\b", re.IGNORECASE)


def apply_aliases(text: str) -> str:
    """Заменяет сленг на формальные термины (по границам слова, регистронезависимо)."""
    return _ALIAS_RE.sub(lambda m: ALIASES[m.group(0).lower()], text or "")


REWRITE_PROMPT = (
    "Ты переписываешь вопрос пользователя в короткий поисковый запрос на формальном русском "
    "для поиска по сайту вуза. Раскрывай сленг и сокращения (например «повышка» → «повышенная "
    "стипендия»). Если вопрос ссылается на предыдущий разговор местоимениями (он, это, там, туда), "
    "подставь, о чём речь. Верни ТОЛЬКО запрос одной строкой, без кавычек и пояснений."
)


async def rewrite_query(question: str, history: list[dict] | None = None) -> str:
    """Переписывает вопрос в формальный поисковый запрос через DeepSeek (с учётом истории).
    При отсутствии ключа/ошибке/подозрительном ответе — возвращает исходный вопрос."""
    if not DEEPSEEK_API_KEY:
        return question

    messages = [{"role": "system", "content": REWRITE_PROMPT}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": question})
    # thinking disabled: переписывание — механическая задача, рассуждение не нужно и только
    # тормозит (≈1с вместо ≈2с). Смысл сленга задаёт пример в REWRITE_PROMPT, а не «мысли».
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.0,
        "thinking": {"type": "disabled"},
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(DEEPSEEK_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        rewritten = data["choices"][0]["message"]["content"].strip().strip('"').strip()
        # Гард: пустой или неадекватно длинный ответ — не доверяем
        if not rewritten or len(rewritten) > 200:
            return question
        return rewritten
    except Exception:
        return question


async def build_search_query(question: str, history: list[dict] | None = None) -> str:
    """Запрос для ретрива: сперва раскрываем сленг (чтобы rewrite не угадывал неверно,
    напр. «доды» → «дни открытых дверей»), затем LLM-rewrite, затем алиасы ещё раз."""
    normalized = apply_aliases(question)
    rewritten = await rewrite_query(normalized, history)
    return apply_aliases(rewritten)
