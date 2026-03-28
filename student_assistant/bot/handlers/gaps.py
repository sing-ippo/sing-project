from datetime import datetime

from babel.dates import format_datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from ..keyboards.inline_keyboards import get_back_to_start_keyboard
from ..suggestions import get_all_suggestions

gaps_router = Router()

@gaps_router.callback_query(F.data == 'suggested_questions')
async def suggested_questions(callback_query: CallbackQuery):
    suggestions_data = await get_all_suggestions()
    if suggestions_data:
        await callback_query.message.edit_text(f'Список предложенных вопросов. Количество: {len(suggestions_data)}')
        for i in suggestions_data:
            dt = format_datetime(datetime.strptime(i["timestamp"], "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None), locale='ru', format='long')[:-3]
            await callback_query.message.answer(f'Вопрос: <i>{i["question"]}</i>\nОт пользователя: <i>{i["user"]}</i>\nБыл предложен {dt}', parse_mode='HTML')
    else:
        await callback_query.message.edit_text('Отсутствуют предложенные вопросы. Зайдите позднее', reply_markup=get_back_to_start_keyboard())

@gaps_router.message(Command("gaps"))
async def suggested_questions(message: Message):
    suggestions_data = await get_all_suggestions()
    if suggestions_data:
        await message.answer(f'Список предложенных вопросов. Количество: {len(suggestions_data)}')
        for i in suggestions_data:
            dt = format_datetime(datetime.strptime(i["timestamp"], "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None), locale='ru', format='long')[:-3]
            await message.answer(f'Вопрос: <i>{i["question"]}</i>\nОт пользователя: <i>{i["user"]}</i>\nБыл предложен {dt}', parse_mode='HTML')
    else:
        await message.answer('Отсутствуют предложенные вопросы. Зайдите позднее', reply_markup=get_back_to_start_keyboard())
