from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import pytz

from ..search_engine import search, NO_ANSWER_TEXT
from ..faq_and_logs import get_possible_options, save_requests
from ..keyboards.inline_keyboards import answer_was_helpful_keyboard, no_answer_provided_keyboard, get_back_to_start_keyboard
from ..suggestions import save_suggestion

faq_router = Router()

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
    question = message.text
    possible_options = await get_possible_options()
    search_results = await search(question, possible_options)
    for i in search_results:
        if i['answer'] == NO_ANSWER_TEXT:
            await message.answer(i['answer'], reply_markup=no_answer_provided_keyboard(i["id"]))
        else:
            await message.answer(i['answer'], reply_markup=answer_was_helpful_keyboard(i['id']))

    await state.clear()
    
    await state.set_state(Answer.results)
    await state.update_data(results=search_results)
    
@faq_router.callback_query(F.data.startswith('helpful_'))
async def answer_helpful_status_handler(callback_query: CallbackQuery, state: FSMContext):
    data = callback_query.data.split('_')
    status, uid = data[1], data[2]
    all_given_answers = await state.get_data()
    all_given_answers = all_given_answers.get('results')
    answer_from_handler = [i for i in all_given_answers if i['id'] == uid][0]

    answer_from_handler["timestamp"] = datetime.now(tz=pytz.timezone("Europe/Moscow")).replace(microsecond=0).isoformat()
    answer_from_handler['matched'] = True
    answer_from_handler['helpful'] = False
    if status == "true":
        answer_from_handler['helpful'] = True
    await save_requests(answer_from_handler) # сохранение данных в файл

    await callback_query.message.edit_text("Спасибо за обратную поддержку!", reply_markup=get_back_to_start_keyboard())

@faq_router.callback_query(F.data.startswith('no-answer_'))
async def no_answer_provided_hadnler(callback_query: CallbackQuery, state: FSMContext):
    data = callback_query.data.split('_')
    status = data[1]
    given_answer = await state.get_data()
    result = given_answer.get('results')[0]

    formatted_result = {
        "timestamp": datetime.now(tz=pytz.timezone("Europe/Moscow")).replace(microsecond=0).isoformat(),
        "user": callback_query.from_user.first_name,
        "type": "new_question",
        "question": result['query'],
        "answer": None
    }
    if status == 'agree':
        await save_suggestion(formatted_result)
        await callback_query.message.edit_text("Спасибо за обратную поддержку!", reply_markup=get_back_to_start_keyboard())
    else:
        await callback_query.message.edit_text('Ну ладно ;(', reply_markup=get_back_to_start_keyboard())


    