import json
import re
from pathlib import Path
from typing import Any

# Search engine Артема

# =========================
# НАСТРОЙКИ
# =========================

MIN_WORD_LEN = 3
DEFAULT_CONFIDENCE_THRESHOLD = 4
DEFAULT_FALLBACK_ANSWER = (
    "Извините, я не смог найти точный ответ в базе знаний. "
    "Попробуйте переформулировать вопрос."
)


# =========================
# РАБОТА С FAQ
# =========================

def split_words(text: str) -> set[str]:
    """Разбивает текст на слова, приводит к нижнему регистру, убирает короткие слова."""
    words = re.findall(r"[а-яА-Яa-zA-Z0-9ёЁ]+", text.lower())
    return {word for word in words if len(word) >= MIN_WORD_LEN}


def compare_word_and_keyword(word: str, keyword_part: str) -> int:
    """
    Вес совпадения:
    4 - точное совпадение
    3 - одно слово входит в другое
    2 - совпадают первые 3 символа
    0 - совпадения нет
    """
    if word == keyword_part:
        return 4

    if word in keyword_part or keyword_part in word:
        return 3

    min_prefix_len = 3
    if len(word) >= min_prefix_len and len(keyword_part) >= min_prefix_len:
        if word[:min_prefix_len] == keyword_part[:min_prefix_len]:
            return 2

    return 0


def calculate_score(question_words: set[str], keywords: list[str]) -> int:
    """Считает общий score для одной FAQ-записи."""
    total_score = 0
    used_keyword_parts = set()

    for keyword in keywords:
        keyword_parts = split_words(keyword)

        for part in keyword_parts:
            best_score_for_part = 0

            for word in question_words:
                score = compare_word_and_keyword(word, part)
                if score > best_score_for_part:
                    best_score_for_part = score

            if best_score_for_part > 0 and part not in used_keyword_parts:
                total_score += best_score_for_part
                used_keyword_parts.add(part)

    return total_score


def search_top_faq(question: str, faq_entries: list[dict], top_n: int = 5) -> list[tuple[int, dict]]:
    """Возвращает top_n FAQ-записей по score."""
    question_words = split_words(question)
    results: list[tuple[int, dict]] = []

    for entry in faq_entries:
        score = calculate_score(question_words, entry.get("keywords", []))
        results.append((score, entry))

    results.sort(key=lambda x: x[0], reverse=True)
    return results[:top_n]


def search_matching_faq(
    question: str,
    faq_entries: list[dict],
    min_score: int = 2,
    top_n: int = 5,
) -> list[tuple[int, dict]]:
    """
    Отсекает слабые совпадения:
    - score < min_score
    - слишком далеко от лучшего результата
    """
    results = search_top_faq(question, faq_entries, top_n=top_n)
    results = [(score, entry) for score, entry in results if score >= min_score]

    if not results:
        return []

    best_score = results[0][0]
    return [(score, entry) for score, entry in results if score >= best_score - 1]


def format_results(results: list[tuple[int, dict]]) -> list[dict]:
    """Приводит результаты к удобному JSON-friendly виду."""
    formatted: list[dict] = []

    for score, entry in results:
        formatted.append(
            {
                "id": entry.get("id"),
                "question": entry.get("question"),
                "answer": entry.get("answer"),
                "score": score,
            }
        )

    return formatted


# =========================
# ОСНОВНОЙ ПОИСК
# =========================

def _search_sync(query: str, faq_data: list[dict], top_n: int = 3) -> list[dict]:
    """
    Синхронная внутренняя версия поиска.
    Возвращает top-N результатов с полями: id, question, answer, score.
    """
    results = search_matching_faq(query, faq_data, min_score=2, top_n=top_n)
    return format_results(results)


async def search(query: str, faq_data: list[dict], top_n: int = 3) -> list[dict]:
    """
    Асинхронная версия под Sprint 4.
    Её можно вызывать через await из FastAPI.
    """
    return _search_sync(query, faq_data, top_n=top_n)


async def search_with_confidence(
    query: str,
    faq_data: list[dict],
    top_n: int = 3,
    confidence_threshold: int = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict:
    """
    Возвращает:
    {
        "results": [...],
        "confident": bool
    }
    """
    top_results = search_top_faq(query, faq_data, top_n=top_n)
    best_score = top_results[0][0] if top_results else 0

    matching_results = search_matching_faq(query, faq_data, min_score=2, top_n=top_n)
    formatted_results = format_results(matching_results)

    return {
        "results": formatted_results,
        "confident": best_score >= confidence_threshold,
    }


# =========================
# УТИЛИТЫ ДЛЯ СЕРВЕРА
# =========================

def load_faq_from_file(path: str | Path | None = None) -> list[dict]:
    """
    Загружает faq.json.
    Если путь не передан, берёт faq.json рядом с этим файлом.
    """
    faq_path = Path(path) if path is not None else Path(__file__).with_name("faq.json")

    with faq_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("faq.json должен содержать список объектов")

    return data


async def get_best_answer(
    query: str,
    faq_data: list[dict],
    top_n: int = 3,
    fallback_answer: str = DEFAULT_FALLBACK_ANSWER,
) -> dict[str, Any]:
    """
    Главная функция для voice_server.py.

    Возвращает словарь вида:
    {
        "question": "...",
        "answer": "...",
        "found": bool,
        "match": {...} | None,
        "results": [...]
    }
    """
    normalized_query = query.strip()
    results = await search(normalized_query, faq_data, top_n=top_n)

    if not results:
        return {
            "question": normalized_query,
            "answer": fallback_answer,
            "found": False,
            "match": None,
            "results": [],
        }

    best_match = results[0]

    return {
        "question": normalized_query,
        "answer": best_match.get("answer", fallback_answer),
        "found": True,
        "match": best_match,
        "results": results,
    }