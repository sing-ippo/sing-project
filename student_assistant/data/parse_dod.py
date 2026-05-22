import json
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent
SOURCES_DIR = BASE_DIR / "sources"

INPUT_PATH = SOURCES_DIR / "dod_raw.json"
OUTPUT_PATH = SOURCES_DIR / "dod_faq.json"

START_ID = 30000
DEFAULT_CATEGORY = "поступление"
DEFAULT_SOURCE = "dod"


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


def load_json(path: str | Path) -> list[dict]:
    path = Path(path)

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            log(f"Ошибка: файл {path} должен содержать список")
            return []

        return data

    except FileNotFoundError:
        log(f"Ошибка: файл не найден: {path}")
        return []

    except json.JSONDecodeError:
        log(f"Ошибка: некорректный JSON: {path}")
        return []


def save_json(data: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def convert_dod_entry(raw_entry: dict, index: int) -> dict:
    return {
        "id": START_ID + index,
        "question": raw_entry.get("question", "").strip(),
        "keywords": raw_entry.get("keywords", []),
        "answer": raw_entry.get("answer", "").strip(),
        "category": DEFAULT_CATEGORY,
        "source": DEFAULT_SOURCE,
    }


def convert_all_dod(raw_entries: list[dict]) -> list[dict]:
    entries = []

    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            continue

        entry = convert_dod_entry(raw_entry, len(entries))
        entries.append(entry)

    return entries


def parse_dod(
    input_path: str | Path = INPUT_PATH,
    output_path: str | Path = OUTPUT_PATH,
) -> list[dict]:
    raw_entries = load_json(input_path)
    entries = convert_all_dod(raw_entries)

    save_json(entries, output_path)

    log(f"Загружено DOD-записей: {len(raw_entries)}")
    log(f"Сохранено FAQ-записей: {len(entries)}")
    log(f"Файл сохранён: {output_path}")

    return entries


def main() -> None:
    parse_dod()


if __name__ == "__main__":
    main()