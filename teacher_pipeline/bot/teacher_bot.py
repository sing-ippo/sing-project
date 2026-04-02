import os
import logging
import asyncio
import socket
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.request import HTTPXRequest
from dotenv import load_dotenv

PROXY_URL = 'http://127.0.0.1:10809'
os.environ['HTTP_PROXY'] = PROXY_URL
os.environ['HTTPS_PROXY'] = PROXY_URL

from pipeline import process_document 

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Здравствуйте! Пришлите мне файл (PDF|TXT|DOCX), и я создам по нему тест."
    )

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    msg = await update.message.reply_text(f"Файл '{doc.file_name}' получен. Генерирую вопросы...")

    if not os.path.exists("downloads"): 
        os.makedirs("downloads")
    
    path = os.path.join("downloads", doc.file_name)
    
    try:
        new_file = await context.bot.get_file(doc.file_id)
        await new_file.download_to_drive(path)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, process_document, path)

        if not result or result.get("error") == "file_too_large_or_empty":
            await msg.edit_text("Ошибка: Файл слишком большой (лимит 50 КБ) или не содержит текста.")
            return
        if not result.get("quiz"):
            await msg.edit_text("Ошибка: Нейросеть не смогла составить вопросы по этому тексту.")
            return
        context.user_data['quiz'] = result['quiz']
        context.user_data['current_step'] = 0
        context.user_data['score'] = 0
        
        await send_question(update, context)

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.message.reply_text(f"Ошибка: {e}")
    finally:
        if os.path.exists(path): 
            os.remove(path)

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    step = data['current_step']
    q = data['quiz'][step]
    
    keyboard = [[
        InlineKeyboardButton("A", callback_data="0"),
        InlineKeyboardButton("B", callback_data="1"),
        InlineKeyboardButton("C", callback_data="2"),
        InlineKeyboardButton("D", callback_data="3")
    ]]
    
    text = f"❓ *Вопрос {step + 1}/{len(data['quiz'])}*\n\n{q['question']}\n\n"
    for i, opt in enumerate(q['options']):
        letter = ["A", "B", "C", "D"][i]
        text += f"*{letter})* {opt}\n"

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = context.user_data
    if 'quiz' not in data or data['current_step'] >= len(data['quiz']):
        return

    q = data['quiz'][data['current_step']]
    user_choice = int(query.data)
    correct_idx = q['correct']
    
    if user_choice == correct_idx:
        status = "✅ *Верно!*"
        data['score'] += 1
    else:
        status = f"❌ *Неверно.*\nПравильный ответ: {q['options'][correct_idx]}"
    
    explanation = f"{status}\n\n💡Объяснение: {q.get('explanation', '')}"
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=explanation,
        parse_mode='Markdown'
    )

    data['current_step'] += 1
    
    if data['current_step'] < len(data['quiz']):
        await send_question(update, context)
    else:
        # Финал
        score = data['score']
        total = len(data['quiz'])
        msg = f"🏁 *Тест завершен!*\nРезультат: {score} из {total} ({int(score/total*100)}%)"
        await context.bot.send_message(update.effective_chat.id, msg, parse_mode='Markdown')
        context.user_data.clear()

def main():
    if not TOKEN:
        print("Ошибка: TOKEN не найден")
        return

    t_request = HTTPXRequest(
        proxy=PROXY_URL, 
        connect_timeout=30, 
        read_timeout=30
    )

    app = (
        Application.builder()
        .token(TOKEN)
        .request(t_request)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(handle_answer))
    
    print(f"Бот запущен через {PROXY_URL}....")
    app.run_polling()

if __name__ == "__main__":
    main()