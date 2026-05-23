from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ..keyboards.inline_keyboards import start_inline_keyboard

start_router = Router()

@start_router.message(Command('start'))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Привет, я AI-ассистент РТУ МИРЭА 🤖. Чем могу помочь?", reply_markup=start_inline_keyboard())

@start_router.callback_query(F.data == "get_back_to_start")
async def get_back_to_start_handler(callback_query: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.answer("Вы вернулись на главную")
    await callback_query.message.delete()
    await callback_query.message.answer("Привет, я AI-ассистент РТУ МИРЭА 🤖. Чем могу помочь?", reply_markup=start_inline_keyboard())