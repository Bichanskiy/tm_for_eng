from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Основная клавиатура с командами"""
    keyboard = [
        [KeyboardButton(text="➕ Добавить задачу")],
        [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="❓ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def remove_keyboard() -> ReplyKeyboardRemove:
    """Убрать клавиатуру"""
    return ReplyKeyboardRemove()