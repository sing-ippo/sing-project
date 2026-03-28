from aiogram.utils.keyboard import InlineKeyboardBuilder

def start_inline_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text='Вопрос', callback_data='question')
    builder.button(text="Предложенные вопросы", callback_data="suggested_questions")
    builder.adjust()
    return builder.as_markup()

def get_back_to_start_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Вернуться на главную", callback_data="get_back_to_start")
    builder.adjust()
    return builder.as_markup()

def answer_was_helpful_keyboard(uid: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="Да", callback_data=f"helpful_true_{uid}")
    builder.button(text="Нет", callback_data=f"helpful_false_{uid}")
    builder.adjust()
    return builder.as_markup()

def no_answer_provided_keyboard(uid: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="Соглашаюсь", callback_data=f"no-answer_agree")
    builder.button(text="Отказываюсь", callback_data=f"no-answer_deny")
    builder.adjust()
    return builder.as_markup()