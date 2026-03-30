import json
import sys
import re

VALID_CATEGORIES = {
    "навигация", "экзамены", "преподаватели", "учебный_процесс", 
    "ит_системы", "бюрократия", "общежитие", "лекции"
}

STATIC_SOURCES = {
    "manual", "chat_экзамены_мирэа", 
    "chat_поступление_иит", "chat_подслушано_мирэа"
}

LECTURE_PATTERN = re.compile(r"^lecture_\d+$")
KEYWORD_PATTERN = re.compile(r"^[а-яёa-z0-9_\s\-\/]+$")

def check_base_fields(entry: dict) -> list[str]: # Валидация Question и Answer

    errors = []
    q = entry.get("question")
    a = entry.get("answer")

    if not isinstance(q, str) or not q.strip():
        errors.append("Поле 'question' должно быть непустой строкой")
    if not isinstance(a, str) or not a.strip():
        errors.append("Поле 'answer' должно быть непустой строкой")
    return errors

def check_keywords(entry: dict) -> list[str]: # Валидация Keywords

    errors = []

    keywords = entry.get("keywords")

    if not isinstance(keywords, list) or len(keywords) == 0:
        errors.append("Поле 'keywords' должно быть непустым списком")
    elif not all(isinstance(i, str) and i.strip() for i in keywords):
        errors.append("Все элементы 'keywords' должны быть непустыми строками")
    else:
        for keyword in keywords:
            if keyword != keyword.lower():
                errors.append(f"keyword '{keyword}' должен быть в нижнем регистре")
            elif not KEYWORD_PATTERN.match(keyword):
                errors.append(f"keyword '{keyword}' содержит недопустимые символы")
    return errors

def check_consistency(entry: dict) -> list[str]: # Кросс-полевая валидация (Consistency Check)

    errors = []

    eid = entry.get("id")
    cat = entry.get("category")
    src = entry.get("source")


    if not isinstance(eid, int): 
        return errors
    if not isinstance(src, str):
        errors.append("Поле 'source' должно быть строкой")
        return errors

    is_lecture_format = bool(LECTURE_PATTERN.match(src))
    is_static_format = src in STATIC_SOURCES

    if not is_static_format and not is_lecture_format:
        errors.append(f"Неверный формат source: '{src}'")

    if cat not in VALID_CATEGORIES:
        errors.append(f"Недопустимая категория: '{cat}'")

    if 1 <= eid <= 999 and src != "manual":
        errors.append(f"Для ID {eid} (бытовой) ожидался source 'manual', получено '{src}'")
    elif 1000 <= eid <= 1999 and cat != "лекции":
        errors.append(f"Для ID {eid} ожидалась категория 'лекции', получено '{cat}'")
    elif eid >= 2000 and not src.startswith("chat_"):
        errors.append(f"Для ID {eid} (чат) источник должен начинаться с 'chat_', получено '{src}'")

    return errors

def validate_entry(entry: dict, seen_ids: set[int]) -> list[str]:
    """Диспетчер, который просто опрашивает все функции по очереди."""
    all_errors = []
    eid = entry.get("id")

    if not isinstance(eid, int):
        all_errors.append(f"ID должен быть int, получено {type(eid).__name__}")
    elif eid in seen_ids:
        all_errors.append(f"ID {eid} не уникален")
    else:
        seen_ids.add(eid)

    check_functions = [
        check_base_fields,
        check_keywords,
        check_consistency
    ]

    for func in check_functions:
        all_errors.extend(func(entry))

    return all_errors

def validate_faq(entries: list[dict]) -> tuple[list[dict], list[str]]:

    valid_faq_list = []
    all_errors = []
    seen_ids = set()

    for index, entry in enumerate(entries):
        entry_errors = validate_entry(entry, seen_ids)
        
        if entry_errors:
            eid = entry.get("id", "None")
            for err in entry_errors:
                all_errors.append(f"Запись #{index} [ID: {eid}]: {err}")
        else:
            valid_faq_list.append(entry)

    return valid_faq_list, all_errors

def main():
    if len(sys.argv) < 2:
        print("Использование: python validate.py <file.json>")
        sys.exit(1)

    filename = sys.argv[1]

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not isinstance(data, list):
            print("Ошибка: Корневой элемент JSON должен быть списком.")
            sys.exit(1)

        valid_data, error_list = validate_faq(data)

        if error_list:
            print(f"Найдено ошибок: {len(error_list)}")
            for error in error_list:
                print(f"  - {error}")
            print(f"\nРезультат: {len(valid_data)} из {len(data)} записей валидны, {len(error_list)} ошибки")
            sys.exit(1)
        else:
            print(f"OK, 0 ошибок (проверено записей: {len(valid_data)})")

    except FileNotFoundError:
        print(f"Ошибка: Файл '{filename}' не найден.")
    except json.JSONDecodeError:
        print(f"Ошибка: Не удалось распарсить JSON в '{filename}'.")
    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")

if __name__ == "__main__":
    main()
