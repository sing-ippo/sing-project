import json
import re
from pathlib import Path
from datetime import datetime
from collections import Counter
from functools import lru_cache

from pymorphy3 import MorphAnalyzer

from convert_lectures import convert_lectures
from convert_chats import convert_chats
from dedup import deduplicate
from validate import validate_faq

import nltk
from nltk.corpus import stopwords


# ================== CONFIG ==================

BASE_DIR = Path(__file__).resolve().parent
SOURCES_DIR = BASE_DIR / "sources"

FILES = {
    "lectures_src": SOURCES_DIR / "lectures.json",
    "lectures_faq": SOURCES_DIR / "lecture_faq.json",
    "chats_src": SOURCES_DIR / "student_questions.json",
    "manual_src": SOURCES_DIR / "faq_manual.json",
    "dod_src": SOURCES_DIR / "dod_raw.json",

    "lectures_output": BASE_DIR / "faq_lectures.json",
    "chats_output": BASE_DIR / "faq_chats.json",

    "output": BASE_DIR / "faq.json",
    "output_with_errors": BASE_DIR / "faq_with_errors.json",
    "report": BASE_DIR / "report.txt",
    "errors_log": BASE_DIR / "errors.log",
}

DEDUP_THRESHOLD = 85

WORD_RE = re.compile(r"[a-zа-яё]+", re.IGNORECASE)

CUSTOM_STOP_KEYWORDS = {
    "и", "в", "во", "на", "по", "с", "со", "к", "ко",
    "а", "но", "или", "это", "как", "что", "для",
    "из", "от", "до", "при", "об", "о", "у", "за",
    "есть", "быть", "также", "можно", "нужно",
    "какой", "какая", "какие", "какого", "какую",
    "когда", "где", "куда", "почему", "зачем",
    "сколько", "чем", "кто", "ли", "мне", "нам",
    "тебе", "вам", "они", "оно", "она", "он",
    "мы", "вы", "я", "ты", "же", "бы", "то",
    "вот", "там", "тут", "тоже", "уже", "еще", "ещё",
    "просто", "вообще", "типа", "всем", "привет",
    "подскажите", "пожалуйста", "ребята", "человек",
    "люди", "который", "которая", "которые", "чтобы",
    "если", "да", "нет"
}

LEMMA_REPLACEMENTS = {
    "военок": "военный",
    "военка": "военный",
    "военком": "военный",
    "общага": "общежитие",
    "препод": "преподаватель",
    "зачет": "зачет",
    "деньга": "деньги",
}

MIN_KEYWORD_LENGTH = 3

ALLOWED_SHORT_KEYWORDS = {
    "егэ",
    "сдо",
    "лк",
    "git",
    "sql",
    "dml",
    "if",
}

morph = MorphAnalyzer()


# ================== UTILS ==================

def build_stop_keywords() -> set[str]:
    try:
        return set(stopwords.words("russian")) | CUSTOM_STOP_KEYWORDS
    except LookupError:
        nltk.download("stopwords", quiet=True)
        return set(stopwords.words("russian")) | CUSTOM_STOP_KEYWORDS


STOP_KEYWORDS = build_stop_keywords()

def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


def safe_load_json(path: str | Path) -> list[dict]:
    path = Path(path)

    if not path.exists():
        return []

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            log(f"❌ Ошибка: файл {path} должен содержать список")
            return []

        return data

    except Exception as e:
        log(f"❌ Ошибка загрузки {path}: {e}")
        return []


def save_json(data: list[dict], path: str | Path) -> None:
    path = Path(path)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    text = text.replace("\n", " ").replace("\t", " ")
    text = text.replace("\r", " ").replace("\xa0", " ")
    text = " ".join(text.split())

    return text.strip()


def get_range(data: list[dict]) -> str:
    if not data:
        return "0"

    ids = [
        item.get("id")
        for item in data
        if isinstance(item, dict) and isinstance(item.get("id"), int)
    ]

    if not ids:
        return "unknown"

    return f"{min(ids)}–{max(ids)}"


def save_errors(errors: list[str]) -> None:
    if not errors:
        return

    with FILES["errors_log"].open("w", encoding="utf-8") as f:
        f.write("\n".join(errors))


# ================== KEYWORD NORMALIZATION ==================

@lru_cache(maxsize=20000)
def normalize_word(word: str) -> str:
    word = word.lower().replace("ё", "е")
    lemma = morph.parse(word)[0].normal_form
    lemma = lemma.replace("ё", "е")

    return LEMMA_REPLACEMENTS.get(lemma, lemma)


def normalize_keyword(keyword: str) -> str:
    if not isinstance(keyword, str):
        return ""

    keyword = clean_text(keyword).lower().replace("ё", "е")

    if not keyword:
        return ""

    words = WORD_RE.findall(keyword)

    if not words:
        return ""

    normalized_words = []

    for word in words:
        normalized_word = normalize_word(word)

        if (
            len(normalized_word) < MIN_KEYWORD_LENGTH
            and normalized_word not in ALLOWED_SHORT_KEYWORDS
        ):
            continue

        if normalized_word in STOP_KEYWORDS:
            continue

        normalized_words.append(normalized_word)

    if not normalized_words:
        return ""

    return " ".join(normalized_words)


def normalize_keywords(keywords) -> list[str]:
    if keywords is None:
        return []

    if isinstance(keywords, str):
        keywords = keywords.replace(";", ",").split(",")

    if not isinstance(keywords, list):
        return []

    normalized_keywords = []
    seen = set()

    for keyword in keywords:
        normalized_keyword = normalize_keyword(keyword)

        if not normalized_keyword:
            continue

        if normalized_keyword in seen:
            continue

        normalized_keywords.append(normalized_keyword)
        seen.add(normalized_keyword)

    return normalized_keywords


def normalize_entry_keywords(entry: dict) -> dict:
    entry = dict(entry)
    entry["keywords"] = normalize_keywords(entry.get("keywords", []))

    return entry


def normalize_all_keywords(entries: list[dict]) -> list[dict]:
    normalized_entries = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        normalized_entries.append(normalize_entry_keywords(entry))

    return normalized_entries


# ================== REPORT ==================

def generate_report(stats: dict, output_path: str | Path) -> None:
    report_lines = [
        "=== Отчёт сборки faq.json ===",
        f"Дата: {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "Источники:"
    ]

    for src, info in stats["sources"].items():
        report_lines.append(
            f"  {src:<11} — {info['count']} записей (id {info['range']})"
        )

    report_lines.append("")
    report_lines.append(f"Дедупликация: удалено {stats['removed']} дублей")
    report_lines.append(f"Валидация: {stats['errors']} ошибок")
    report_lines.append("")
    report_lines.append(f"Итого: {stats['total']} записей")

    cat_stats = Counter(stats["categories"])
    sorted_cats = sorted(cat_stats.items(), key=lambda x: x[1], reverse=True)
    cat_str = ", ".join([f"{name} ({count})" for name, count in sorted_cats])

    report_lines.append(f"Категории: {cat_str}")

    output_path = Path(output_path)

    with output_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print("\n".join(report_lines))


# ================== PIPELINE ==================

def load_data() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    log("📥 Загрузка данных...")

    lectures = convert_lectures(
        lectures_path=FILES["lectures_src"],
        faq_path=FILES["lectures_faq"],
        output_path=FILES["lectures_output"],
    ) or []

    chats = convert_chats(
        chat_path=FILES["chats_src"],
        output_path=FILES["chats_output"],
    ) or []

    manual = safe_load_json(FILES["manual_src"])
    dod = safe_load_json(FILES["dod_src"])

    return manual, lectures, chats, dod


def merge_data(
    manual: list[dict],
    lectures: list[dict],
    chats: list[dict],
    dod: list[dict]
) -> list[dict]:
    log("🔗 Слияние данных...")
    return manual + lectures + chats + dod


def process_data(full_list: list[dict]) -> tuple[list[dict], list[dict], int, list[str]]:
    log("🔤 Нормализация keywords...")

    normalized_list = normalize_all_keywords(full_list)

    log("🧹 Дедупликация...")

    unique_data, removed_count = deduplicate(
        normalized_list,
        threshold=DEDUP_THRESHOLD,
    )

    log("✅ Валидация...")

    valid_entries, errors = validate_faq(unique_data)

    return unique_data, valid_entries, removed_count, errors


def build_stats(
    manual: list[dict],
    lectures: list[dict],
    chats: list[dict],
    dod: list[dict],
    valid_entries: list[dict],
    removed: int,
    errors: list[str]
) -> dict:
    return {
        "sources": 
        {
            "manual": 
            {
                "count": len(manual),
                "range": get_range(manual),
            },
            "lectures": 
            {
                "count": len(lectures),
                "range": get_range(lectures),
            },
            "chats": 
            {
                "count": len(chats),
                "range": get_range(chats),
            },
            "dod": 
            {
                "count": len(dod),
                "range": get_range(dod),
            }
        },
        "removed": removed,
        "errors": len(errors),
        "total": len(valid_entries),
        "categories": [
            entry.get("category", "unknown")
            for entry in valid_entries
        ],
    }


def save_results(valid_entries: list[dict], errors: list[str]) -> None:
    if errors:
        log("⚠️ Есть ошибки — сохраняем в отдельный файл")
        output_file = FILES["output_with_errors"]
    else:
        output_file = FILES["output"]

    save_json(valid_entries, output_file)

    log(f"💾 Сохранено: {output_file}")

    save_errors(errors)

    if errors:
        log(f"⚠️ Всего ошибок: {len(errors)} (см. {FILES['errors_log']})")

        for error in errors[:5]:
            log(f"  ! {error}")


# ================== MAIN ==================

def build() -> list[dict]:
    log("🚀 Запуск пайплайна сборки базы знаний SING...")

    manual, lectures, chats, dod = load_data()

    full_list = merge_data(
        manual=manual,
        lectures=lectures,
        chats=chats,
        dod=dod
    )

    _, valid_entries, removed_count, errors = process_data(full_list)

    stats = build_stats(
        manual=manual,
        lectures=lectures,
        chats=chats,
        dod=dod,
        valid_entries=valid_entries,
        removed=removed_count,
        errors=errors,
    )

    generate_report(stats, FILES["report"])
    save_results(valid_entries, errors)

    if not errors:
        log("✅ Сборка успешно завершена")
    else:
        log("⚠️ Сборка завершена с ошибками")

    return valid_entries


if __name__ == "__main__":
    build()