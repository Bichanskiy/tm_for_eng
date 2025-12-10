from aiogram import Router, types
from aiogram.filters import Command
from app.database.dao.user import UserDAO
from app.keyboards.reply import get_main_keyboard

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    # Создаем/получаем пользователя
    user = await UserDAO.get_or_create_user(message.from_user)

    welcome_text = (
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я бот для управления задачами. Вот что я умею:\n\n"
        "📋 <b>Основные функции:</b>\n"
        "• Добавлять задачи\n"
        "• Просматривать и редактировать задачи\n"
        "• Отслеживать статусы выполнения\n"
        "• Устанавливать сроки выполнения\n\n"
        "Используйте кнопки ниже для быстрого доступа к функциям!"
    )

    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )