from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import time

from app.database.dao.user import UserDAO
from app.keyboards.reply import get_main_keyboard

router = Router()


class SettingsStates(StatesGroup):
    waiting_for_reminder_time = State()


def get_settings_keyboard(reminders_enabled: bool) -> types.InlineKeyboardMarkup:
    """Клавиатура настроек"""
    toggle_text = "🔕 Выключить напоминания" if reminders_enabled else "🔔 Включить напоминания"

    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=toggle_text, callback_data="toggle_reminders")],
        [types.InlineKeyboardButton(text="⏰ Изменить время сводки", callback_data="change_reminder_time")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="close_settings")]
    ])


@router.message(lambda message: message.text == "⚙️ Настройки")
async def cmd_settings(message: types.Message):
    user = await UserDAO.get_or_create_user(message.from_user)

    reminder_status = "включены ✅" if user.reminders_enabled else "выключены ❌"
    reminder_time_str = user.reminder_time.strftime("%H:%M") if user.reminder_time else "09:00"

    settings_text = (
        "⚙️ <b>Настройки напоминаний</b>\n\n"
        f"🔔 Напоминания: {reminder_status}\n"
        f"⏰ Время утренней сводки: {reminder_time_str}\n"
        f"📅 Напоминание до дедлайна: за {user.remind_before_hours} ч.\n\n"
        "Выберите, что хотите изменить:"
    )

    await message.answer(
        settings_text,
        parse_mode="HTML",
        reply_markup=get_settings_keyboard(user.reminders_enabled)
    )


@router.callback_query(F.data == "toggle_reminders")
async def toggle_reminders(callback: types.CallbackQuery):
    user = await UserDAO.get_or_create_user(callback.from_user)

    # Переключаем состояние
    new_state = not user.reminders_enabled
    await UserDAO.update_reminder_settings(user.id, reminders_enabled=new_state)

    status = "включены ✅" if new_state else "выключены ❌"
    await callback.answer(f"Напоминания {status}")

    # Обновляем сообщение
    user = await UserDAO.get_or_create_user(callback.from_user)
    reminder_time_str = user.reminder_time.strftime("%H:%M") if user.reminder_time else "09:00"

    settings_text = (
        "⚙️ <b>Настройки напоминаний</b>\n\n"
        f"🔔 Напоминания: {status}\n"
        f"⏰ Время утренней сводки: {reminder_time_str}\n"
        f"📅 Напоминание до дедлайна: за {user.remind_before_hours} ч.\n\n"
        "Выберите, что хотите изменить:"
    )

    await callback.message.edit_text(
        settings_text,
        parse_mode="HTML",
        reply_markup=get_settings_keyboard(new_state)
    )


@router.callback_query(F.data == "change_reminder_time")
async def change_reminder_time(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsStates.waiting_for_reminder_time)

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="07:00"), types.KeyboardButton(text="08:00")],
            [types.KeyboardButton(text="09:00"), types.KeyboardButton(text="10:00")],
            [types.KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await callback.message.answer(
        "⏰ Введите время для утренней сводки в формате ЧЧ:ММ\n"
        "Или выберите из предложенных вариантов:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.message(SettingsStates.waiting_for_reminder_time)
async def process_reminder_time(message: types.Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await message.answer(
            "Настройка отменена",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return

    try:
        hours, minutes = map(int, message.text.split(":"))
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            raise ValueError

        new_time = time(hours, minutes)

    except (ValueError, AttributeError):
        await message.answer(
            "❌ Неверный формат! Введите время в формате ЧЧ:ММ\n"
            "Например: 09:00"
        )
        return

    user = await UserDAO.get_or_create_user(message.from_user)
    await UserDAO.update_reminder_settings(user.id, reminder_time=new_time)

    await message.answer(
        f"✅ Время утренней сводки изменено на {message.text}",
        reply_markup=get_main_keyboard()
    )
    await state.clear()


@router.callback_query(F.data == "close_settings")
async def close_settings(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()