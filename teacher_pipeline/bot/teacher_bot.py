import os
from dotenv import load_dotenv
load_dotenv()

# 1. Сначала прокси
PROXY_URL = os.getenv("PROXY_URL")
if PROXY_URL:
    os.environ['HTTP_PROXY'] = PROXY_URL
    os.environ['HTTPS_PROXY'] = PROXY_URL
import random
import logging
import json
import asyncio
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.request import HTTPXRequest

# 2. Потом импорт
from pipeline import process_document, generate_quiz_from_faq

TOKEN = os.getenv("TELEGRAM_TOKEN")
FAQ_PATH = Path(__file__).resolve().parent.parent.parent / "student_assistant" / "data" / "lecture_faq.json"

logging.basicConfig(level=logging.INFO)

def normalize_text(value: str) -> str:
    return " ".join(str(value).strip().casefold().split())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Здравствуйте! Я могу составить вам квиз*\n\n"
        "📄 Отправьте *.txt файл* — и я сгенерирую тест по нему\n"
        "📚 Или используйте */categories* — чтобы выбрать раздел и тему из базы знаний\n"
        "⚡ Также можно сразу вызвать квиз: */quiz_faq <категория>*\n\n"
        "Пример:\n"
        "`/quiz_faq Python`",
        parse_mode="Markdown"
    )

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not FAQ_PATH.exists():
        await update.message.reply_text("❌ FAQ не найден")
        return

    with open(FAQ_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)

    categories = get_available_categories(entries)

    keyboard = [
        [InlineKeyboardButton(cat, callback_data=f"cat:{cat}")]
        for cat in categories
    ]

    await update.message.reply_text(
        "Выберите категорию:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    q = data["quiz"][data["current_step"]]

    kb = [[
        InlineKeyboardButton(["A", "B", "C", "D"][i], callback_data=str(i))
        for i in range(len(q["options"]))
    ]]

    text = f"❓ Вопрос {data['current_step'] + 1}\n\n{q['question']}\n\n"
    for i, opt in enumerate(q["options"]):
        text += f"{['A', 'B', 'C', 'D'][i]}) {opt}\n"

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(kb)
    )

def normalize_category(value: str) -> str:
    return " ".join(str(value).strip().casefold().split())

def get_available_categories(entries):
    categories = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        category = entry.get("category", "")
        if isinstance(category, str) and category.strip():
            categories.add(category.strip())
    return sorted(categories, key=str.casefold)

def filter_entries_by_category(entries, category: str):
    wanted = normalize_category(category)
    filtered = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        entry_category = entry.get("category", "")
        if normalize_category(entry_category) == wanted:
            filtered.append(entry)

    return filtered

async def quiz_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not FAQ_PATH.exists():
        await update.message.reply_text(f"❌ faq.json не найден: {FAQ_PATH}")
        return

    try:
        with open(FAQ_PATH, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except json.JSONDecodeError:
        await update.message.reply_text("❌ faq.json содержит некорректный JSON")
        return

    if not isinstance(entries, list):
        await update.message.reply_text("❌ faq.json должен содержать список FAQ-записей")
        return

    all_entries = entries

    category = " ".join(context.args).strip() if context.args else ""

    if category:
        entries = filter_entries_by_category(all_entries, category)

        if not entries:
            available = get_available_categories(all_entries)
            categories_text = ", ".join(available) if available else "категории не найдены"
            await update.message.reply_text(
                f"❌ В категории «{category}» нет FAQ-записей.\n"
                f"Доступные категории: {categories_text}"
            )
            return
    random.shuffle(entries)
    entries = entries[:15]
    msg = await update.message.reply_text("⏳ Генерирую квиз из базы знаний...")

    loop = asyncio.get_event_loop()
    quiz = await loop.run_in_executor(None, generate_quiz_from_faq, entries)

    if quiz:
        context.user_data.update({
            "quiz": quiz,
            "current_step": 0,
            "score": 0
        })
        await send_question(update, context)
    else:
        await msg.edit_text("❌ Ошибка генерации квиза.")

def deduplicate_quiz(quiz):
    seen = set()
    result = []

    for q in quiz:
        question = q.get("question", "").strip().casefold()
        if question and question not in seen:
            seen.add(question)
            result.append(q)

    return result

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    os.makedirs("downloads", exist_ok=True)
    path = f"downloads/{doc.file_name}"
    
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(path)
    
    msg = await update.message.reply_text("🚀 Обрабатываю файл через ИИ...")
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, process_document, path)
    
    if res.get("quiz"):
        quiz = deduplicate_quiz(res["quiz"])
        random.shuffle(quiz)

        context.user_data.update({
            "quiz": quiz,
            "current_step": 0,
            "score": 0
        })
        await send_question(update, context)
    else:
        await msg.edit_text("❌ Не удалось создать тест.")
    
    if os.path.exists(path): os.remove(path)

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = context.user_data
    q = data['quiz'][data['current_step']]

    is_correct = int(query.data) == q['correct']
    if is_correct:
        data['score'] += 1

    res_text = "✅ Верно!" if is_correct else f"❌ Нет. Правильно: {q['options'][q['correct']]}"

    await context.bot.send_message(
        update.effective_chat.id,
        f"{res_text}\n\n💡 {q.get('explanation','')}"
    )

    data['current_step'] += 1

    if data['current_step'] < len(data['quiz']):
        await send_question(update, context)
    else:
        await context.bot.send_message(
            update.effective_chat.id,
            f"🏁 Тест окончен! {data['score']}/{len(data['quiz'])}"
        )

async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category = query.data.replace("cat:", "", 1)
    context.user_data["selected_category"] = category

    with open(FAQ_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)

    topics = get_available_topics(entries, category)

    if not topics:
        await query.edit_message_text("❌ В этой категории нет тем.")
        return

    keyboard = [
        [InlineKeyboardButton(topic, callback_data=f"topic:{topic}")]
        for topic in topics
    ]

    await query.edit_message_text(
        f"Категория: {category}\n\nВыбери тему:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def filter_entries_by_category_and_topic(entries, category, topic):
    return [
        entry for entry in entries
        if normalize_text(entry.get("category", "")) == normalize_text(category)
        and normalize_text(entry.get("topic", "")) == normalize_text(topic)
    ]


def get_available_topics(entries, category):
    return sorted(
        set(
            entry.get("topic")
            for entry in entries
            if isinstance(entry, dict)
            and normalize_text(entry.get("category", "")) == normalize_text(category)
            and entry.get("topic")
        )
    )

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    topic = query.data.replace("topic:", "", 1)
    category = context.user_data.get("selected_category")

    if not category:
        await query.edit_message_text("❌ Сначала выбери категорию через /categories")
        return

    with open(FAQ_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)

    entries = filter_entries_by_category_and_topic(entries, category, topic)

    if not entries:
        await query.edit_message_text("❌ В этой теме нет вопросов.")
        return

    await query.edit_message_text(
        f"⏳ Генерирую квиз\n\nКатегория: {category}\nТема: {topic}"
    )

    loop = asyncio.get_event_loop()
    quiz = await loop.run_in_executor(None, generate_quiz_from_faq, entries)

    if quiz:
        context.user_data.update({
            "quiz": quiz,
            "current_step": 0,
            "score": 0,
            "selected_topic": topic
        })
        await send_question(update, context)
    else:
        await query.edit_message_text("❌ Ошибка генерации квиза.")

def main():
    req = HTTPXRequest(proxy=PROXY_URL) if PROXY_URL else None
    app = Application.builder().token(TOKEN).request(req).build()
    
    app.add_handler(CommandHandler("start", start))

    app.add_handler(CommandHandler("categories", show_categories))
    app.add_handler(CallbackQueryHandler(handle_category, pattern="^cat:"))
    app.add_handler(CallbackQueryHandler(handle_topic, pattern="^topic:"))

    app.add_handler(CommandHandler("quiz_faq", quiz_faq))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(handle_answer, pattern="^[0-3]$"))
    
    print("🚀 БОТ ЗАПУЩЕН")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
