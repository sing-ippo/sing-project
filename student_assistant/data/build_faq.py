import json
import os
from datetime import datetime
from collections import Counter

from convert_lectures import convert_lectures
from convert_chats import convert_chats
from dedup import deduplicate
from validate import validate_faq


# ================== CONFIG ==================
FILES = {
    "lectures_src": "sources/lectures.json",
    "lectures_faq": "sources/lecture_faq.json",
    "chats_src": "sources/student_questions.json",
    "manual_src": "sources/faq_manual.json",
    "output": "faq.json",
    "output_with_errors": "faq_with_errors.json",
    "report": "report.txt",
    "errors_log": "errors.log"
}

DEDUP_THRESHOLD = 85


# ================== UTILS ==================
def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


def safe_load_json(path):
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"❌ Ошибка загрузки {path}: {e}")
        return []


def get_range(data):
    if not data:
        return "0"

    ids = [item.get("id") for item in data if isinstance(item, dict) and "id" in item]
    if not ids:
        return "unknown"

    return f"{min(ids)}–{max(ids)}"


def save_errors(errors):
    if not errors:
        return

    with open(FILES["errors_log"], "w", encoding="utf-8") as f:
        f.write("\n".join(errors))


# ================== REPORT ==================
def generate_report(stats, output_path):
    report_lines = [
        "=== Отчёт сборки faq.json ===",
        f"Дата: {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "Источники:"
    ]

    for src, info in stats['sources'].items():
        report_lines.append(
            f"  {src:<11} — {info['count']} записей (id {info['range']})"
        )

    report_lines.append("")
    report_lines.append(f"Дедупликация: удалено {stats['removed']} дублей")
    report_lines.append(f"Валидация: {stats['errors']} ошибок")
    report_lines.append("")
    report_lines.append(f"Итого: {stats['total']} записей")

    cat_stats = Counter(stats['categories'])
    sorted_cats = sorted(cat_stats.items(), key=lambda x: x[1], reverse=True)
    cat_str = ", ".join([f"{name} ({count})" for name, count in sorted_cats])

    report_lines.append(f"Категории: {cat_str}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print("\n".join(report_lines))


# ================== PIPELINE ==================
def load_data():
    log("📥 Загрузка данных...")

    # Проверка обязательных файлов
    for key in ["lectures_src", "chats_src"]:
        if not os.path.exists(FILES[key]):
            raise FileNotFoundError(f"Файл не найден: {FILES[key]}")

    lect_data = convert_lectures(
        FILES["lectures_src"],
        FILES["lectures_faq"]
    ) or []
    chat_data = convert_chats(
        FILES["chats_src"],
        min_frequency=3
    ) or []

    manual_data = safe_load_json(FILES["manual_src"])

    return manual_data, lect_data, chat_data


def merge_data(manual, lectures, chats):
    log("🔗 Слияние данных...")
    return manual + lectures + chats


def process_data(full_list):
    log("🧹 Дедупликация...")
    unique_data, removed_count = deduplicate(
        full_list,
        threshold=DEDUP_THRESHOLD
    )

    log("✅ Валидация...")
    valid_entries, errors = validate_faq(unique_data)

    return unique_data, valid_entries, removed_count, errors


def build_stats(manual, lectures, chats, valid_entries, removed, errors):
    return {
        "sources": {
            "manual": {
                "count": len(manual),
                "range": get_range(manual)
            },
            "lectures": {
                "count": len(lectures),
                "range": get_range(lectures)
            },
            "chats": {
                "count": len(chats),
                "range": get_range(chats)
            }
        },
        "removed": removed,
        "errors": len(errors),
        "total": len(valid_entries),
        "categories": [
            e.get('category', 'unknown') for e in valid_entries
        ]
    }


def save_results(valid_entries, errors):
    if errors:
        log("⚠️ Есть ошибки — сохраняем в отдельный файл")
        output_file = FILES["output_with_errors"]
    else:
        output_file = FILES["output"]

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(valid_entries, f, ensure_ascii=False, indent=4)

    log(f"💾 Сохранено: {output_file}")

    save_errors(errors)

    if errors:
        log(f"⚠️ Всего ошибок: {len(errors)} (см. {FILES['errors_log']})")
        for err in errors[:5]:
            log(f"  ! {err}")


# ================== MAIN ==================
def build():
    log("🚀 Запуск пайплайна сборки базы знаний SING...")

    manual, lectures, chats = load_data()
    full_list = merge_data(manual, lectures, chats)

    _, valid_entries, removed_count, errors = process_data(full_list)

    stats = build_stats(
        manual,
        lectures,
        chats,
        valid_entries,
        removed_count,
        errors
    )

    generate_report(stats, FILES["report"])
    save_results(valid_entries, errors)

    if not errors:
        log("✅ Сборка успешно завершена")
    else:
        log("⚠️ Сборка завершена с ошибками")


if __name__ == "__main__":
    build()