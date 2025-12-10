from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart

from app.database.dao.user import UserDAO


router = Router()

@router.message(CommandStart())
async def start_handler(message: Message):
    user = await UserDAO.get_or_create_user(message.from_user)

    await message.answer(
        f"Привет, {user.username or 'пользователь'}!"
    )


@router.message()
async def echo_message(message: Message) -> None:
    await message.reply(message.text)
