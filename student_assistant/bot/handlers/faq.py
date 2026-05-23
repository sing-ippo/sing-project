from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import pytz

from search_engine import search, NO_ANSWER_TEXT
from faq_and_logs import get_possible_options, save_requests
from keyboards.inline_keyboards import answer_was_helpful_keyboard, no_answer_provided_keyboard, get_back_to_start_keyboard
from suggestions import save_suggestion

faq_router = Router()

MSK = pytz.timezone("Europe/Moscow")


def _now_iso() -> str:
    return datetime.now(tz=MSK).replace(microsecond=0).isoformat()


class Question(StatesGroup):
    name = State()


class Answer(StatesGroup):
    results = State()


@faq_router.callback_query(F.data == 'question')
async def question_answer(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(Question.name)
    await callback_query.message.edit_text('Задайте интересующий Вас вопрос... 💬')


@faq_router.message(Question.name)
async def proccess_question(message: Message, state: FSMContext):
    query = message.text or ""
    possible_options = await get_possible_options()
    search_results = await search(query, possible_options)

    await state.set_state(Answer.results)
    await state.update_data(results=search_results, query=query)

    # Текущий search() возвращает [] на промах — это «ответ не найден».
    if not search_results:
        await message.answer(NO_ANSWER_TEXT, reply_markup=no_answer_provided_keyboard("0"))
        return

    for item in search_results:
        await message.answer(item['answer'], reply_markup=answer_was_helpful_keyboard(item['id']))


@faq_router.callback_query(F.data.startswith('helpful_'))
async def answer_helpful_status_handler(callback_query: CallbackQuery, state: FSMContext):
    _, status, uid = callback_query.data.split('_')
    data = await state.get_data()
    results = data.get('results') or []
    match = next((i for i in results if str(i['id']) == uid), None)

    if match:
        record = {
            "timestamp": _now_iso(),
            "query": data.get('query', ''),
            "answer": match.get('answer', ''),
            "matched": True,
            "helpful": status == "true",
            "source": "faq-bot",
        }
        await save_requests(record)

    await callback_query.message.edit_text("Спасибо за обратную связь!", reply_markup=get_back_to_start_keyboard())


@faq_router.callback_query(F.data.startswith('no-answer_'))
async def no_answer_provided_handler(callback_query: CallbackQuery, state: FSMContext):
    status = callback_query.data.split('_')[1]
    data = await state.get_data()
    query = data.get('query', '')

    if status == 'agree':
        suggestion = {
            "timestamp": _now_iso(),
            "user": callback_query.from_user.first_name,
            "type": "new_question",
            "question": query,
            "answer": None,
        }
        await save_suggestion(suggestion)
        await callback_query.message.edit_text("Спасибо! Записали ваш вопрос.", reply_markup=get_back_to_start_keyboard())
    else:
        await callback_query.message.edit_text('Хорошо ;)', reply_markup=get_back_to_start_keyboard())
