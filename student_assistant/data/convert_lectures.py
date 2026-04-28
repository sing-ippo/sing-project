import json
from pathlib import Path
import re
from datetime import datetime

# ================== CONFIG ==================

BASE_DIR = Path(__file__).resolve().parent
SOURCES_DIR = BASE_DIR / "sources"

LECTURES_PATH = SOURCES_DIR / "lectures.json"
LECTURE_FAQ_PATH = SOURCES_DIR / "lecture_faq.json"
OUTPUT_PATH = BASE_DIR / "faq_lectures.json"

MIN_LENGTH_WORD = 3
START_ID = 1000
WORD_PATTERN = re.compile(r'^[a-zа-яё]+(?:-[a-zа-яё]+)*$')

def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def load_json(path: str | Path) -> list:
    path = Path(path)

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            log(f"Ошибка: файл {path} должен содержать список")
            return []

        return data

    except FileNotFoundError:
        log(f"Предупреждение: файл не найден: {path}")
        return []

    except json.JSONDecodeError:
        log(f"Ошибка: файл {path} содержит некорректный JSON")
        return []


def save_json(data: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_clean_keywords(text_list: list[str]) -> list[str]:
    if not text_list:
        return []

    unique_words = {}

    for text in text_list:
        if not isinstance(text, str):
            continue

        tokens = re.findall(r"[a-zа-яё]+(?:-[a-zа-яё]+)*", text.lower())

        for word in tokens:
            clean_word = word.lower().strip()

            if len(clean_word) < MIN_LENGTH_WORD:
                continue

            if WORD_PATTERN.fullmatch(clean_word):
                unique_words[clean_word] = None

    return list(unique_words.keys())

def convert_lectures(
    lectures_path: str | Path,
    faq_path: str | Path,
    output_path: str | Path = OUTPUT_PATH
) -> list[dict]:
    combined_data = []
    current_id = START_ID

    lectures_list = load_json(lectures_path)
    faqs = load_json(faq_path)

    lectures_lookup = {
        lecture["id"]: get_clean_keywords(lecture.get("key_points", []))
        for lecture in lectures_list
    }

    for item in faqs:
        l_id = item.get("lecture_id")
        q_text = item.get("question", "")
        a_text = item.get("answer", "")

        lecture_keywords = lectures_lookup.get(l_id, [])
        question_keywords = get_clean_keywords([q_text])

        keywords = list(dict.fromkeys(lecture_keywords + question_keywords))

        combined_data.append({
            "id": current_id,
            "question": q_text,
            "keywords": keywords,
            "answer": a_text,
            "category": "лекции",
            "source": f"lecture_{l_id}"
        })

        current_id += 1

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(combined_data, f, ensure_ascii=False, indent=4)

    return combined_data


if __name__ == "__main__":
    convert_lectures(
        lectures_path=LECTURES_PATH,
        faq_path=LECTURE_FAQ_PATH,
        output_path=OUTPUT_PATH
    )