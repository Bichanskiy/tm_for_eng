from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta

from app.database.dao.task import TaskDAO
from app.database.dao.user import UserDAO
from app.database.dao.gamification import GamificationDAO
from app.database.enums import TaskStatus
from app.constants.gamification import (
    ACHIEVEMENTS,
    get_random_completion_phrase,
    get_streak_phrase,
    get_random_streak_lost_phrase,
    get_task_xp,
    get_level_emoji,
)
from app.keyboards.inline import (
    get_task_detail_keyboard,
    get_tasks_keyboard,
    get_edit_task_keyboard,
    get_confirmation_keyboard,
)
from app.keyboards.reply import get_main_keyboard

router = Router()


class EditTaskStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_priority = State()
    waiting_for_due_date = State()


@router.callback_query(F.data.startswith("task_"))
async def show_task_detail(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    user = await UserDAO.get_or_create_user(callback.from_user)

    task = await TaskDAO.get_task(task_id, user.id)

    if not task:
        await callback.answer("Задача не найдена!", show_alert=True)
        return

    status_display = {
        "pending": "⏳ Ожидает",
        "in_progress": "🔄 В работе",
        "completed": "✅ Выполнена",
        "cancelled": "❌ Отменена"
    }.get(task.status, task.status)

    priority_stars = "⭐" * min(task.priority, 5)

    task_text = (
        f"📋 <b>Детали задачи</b>\n\n"
        f"<b>Название:</b> {task.title}\n"
        f"<b>Описание:</b>\n{task.description}\n\n"
        f"<b>Статус:</b> {status_display}\n"
        f"<b>Приоритет:</b> {priority_stars} ({task.priority}/10)\n"
        f"<b>Создана:</b> {task.created_at.strftime('%d.%m.%Y %H:%M')}\n"
    )

    if task.due_date:
        due_date_str = task.due_date.strftime('%d.%m.%Y')
        task_due_date = task.due_date.date()
        today = datetime.now().date()
        if task_due_date < today and task.status != TaskStatus.COMPLETED:
            due_date_str += " 🔴 Просрочена!"
        elif task_due_date == today:
            due_date_str += " ⚠️ Сегодня!"
        task_text += f"<b>Срок:</b> {due_date_str}\n"

    if task.completed_at:
        task_text += f"<b>Завершена:</b> {task.completed_at.strftime('%d.%m.%Y %H:%M')}\n"

    await callback.message.edit_text(
        task_text,
        parse_mode="HTML",
        reply_markup=get_task_detail_keyboard(task_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("page_"))
async def handle_pagination(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[1])
    user = await UserDAO.get_or_create_user(callback.from_user)

    tasks = await TaskDAO.get_tasks(
        user_id=user.id,
        limit=TaskDAO.TASKS_PER_PAGE,
        offset=page * TaskDAO.TASKS_PER_PAGE
    )

    if not tasks:
        await callback.answer("Больше нет задач!", show_alert=True)
        return

    total_tasks = await TaskDAO.count_tasks(user.id)
    total_pages = (total_tasks + TaskDAO.TASKS_PER_PAGE - 1) // TaskDAO.TASKS_PER_PAGE

    tasks_text = "📋 <b>Ваши задачи:</b>\n\n"
    for i, task in enumerate(tasks, 1):
        status_icons = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅",
            "cancelled": "❌"
        }

        due_text = ""
        if task.due_date:
            task_due_date = task.due_date.date()
            today = datetime.now().date()
            if task_due_date < today and task.status != TaskStatus.COMPLETED:
                due_text = " 🔴"
            elif task_due_date == today:
                due_text = " ⚠️"
            else:
                due_text = f" 📅 {task.due_date.strftime('%d.%m')}"

        tasks_text += (
            f"{i}. {status_icons.get(task.status, '📝')} "
            f"<b>{task.title}</b>{due_text}\n"
            f"   Приоритет: {task.priority}/10\n\n"
        )

    tasks_text += f"\nСтраница {page + 1}/{total_pages}"

    await callback.message.edit_text(
        tasks_text,
        parse_mode="HTML",
        reply_markup=get_tasks_keyboard(tasks, page=page, total_pages=total_pages)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("done_"))
async def mark_task_done(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    user = await UserDAO.get_or_create_user(callback.from_user)

    # Получаем задачу до обновления
    task = await TaskDAO.get_task(task_id, user.id)
    if not task:
        await callback.answer("Задача не найдена!", show_alert=True)
        return

    # Проверяем, была ли задача уже выполнена
    if task.status == TaskStatus.COMPLETED:
        await callback.answer("Задача уже выполнена!", show_alert=True)
        return

    # Отмечаем задачу выполненной
    updated_task = await TaskDAO.mark_status(
        task_id=task_id,
        user_id=user.id,
        status=TaskStatus.COMPLETED
    )

    if not updated_task:
        await callback.answer("Ошибка при обновлении задачи!", show_alert=True)
        return

    # === ГЕЙМИФИКАЦИЯ ===

    # Рассчитываем XP
    now = datetime.utcnow()
    is_on_time = task.due_date is None or now <= task.due_date
    is_same_day = task.created_at.date() == now.date()
    xp_earned = get_task_xp(task.priority, is_on_time, is_same_day)

    # Добавляем XP
    new_xp, new_level, leveled_up = await GamificationDAO.add_xp(user.id, xp_earned)

    # Обновляем стрик
    new_streak, streak_lost, old_streak = await GamificationDAO.update_streak(user.id)

    # Увеличиваем счётчик выполненных
    await GamificationDAO.increment_completed(user.id)

    # Проверяем достижения
    new_achievements = await GamificationDAO.check_and_unlock_achievements(user.id, task)

    # Формируем сообщение
    message_parts = [get_random_completion_phrase()]
    message_parts.append(f"\n\n✅ <b>{task.title}</b>")
    message_parts.append(f"\n\n💫 <b>+{xp_earned} XP</b>")

    # Бонусы
    bonuses = []
    if is_on_time and task.due_date:
        bonuses.append("⏰ Вовремя")
    if is_same_day:
        bonuses.append("⚡ В тот же день")
    if task.priority >= 8:
        bonuses.append("🎯 Высокий приоритет")

    if bonuses:
        message_parts.append(f"\n   ({', '.join(bonuses)})")

    # Сообщение о повышении уровня
    if leveled_up:
        level_emoji = get_level_emoji(new_level)
        message_parts.append(f"\n\n🎉 <b>НОВЫЙ УРОВЕНЬ: {new_level}!</b> {level_emoji}")

    # Сообщение о стрике
    if streak_lost and old_streak > 1:
        message_parts.append(f"\n\n{get_random_streak_lost_phrase()}")
        message_parts.append(f"\n(Был: {old_streak} дней)")
    else:
        streak_phrase = get_streak_phrase(new_streak)
        if streak_phrase:
            message_parts.append(f"\n\n{streak_phrase}")
        elif new_streak > 1:
            message_parts.append(f"\n\n🔥 Стрик: {new_streak} дней подряд!")

    # Сообщение о новых достижениях
    total_achievement_xp = 0
    if new_achievements:
        message_parts.append("\n\n🏆 <b>Новые достижения:</b>")
        for ach_id in new_achievements:
            ach = ACHIEVEMENTS.get(ach_id)
            if ach:
                message_parts.append(f"\n{ach.icon} <b>{ach.name}</b>")
                if ach.xp_reward > 0:
                    message_parts.append(f" (+{ach.xp_reward} XP)")
                    total_achievement_xp += ach.xp_reward

        # Добавляем XP за достижения
        if total_achievement_xp > 0:
            await GamificationDAO.add_xp(user.id, total_achievement_xp)

    # Отправляем сообщение с результатами
    await callback.message.answer(
        "".join(message_parts),
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

    # Обновляем детали задачи
    # Создаём новый callback_data для показа обновлённой задачи
    callback.data = f"task_{task_id}"
    await show_task_detail(callback)


@router.callback_query(F.data.startswith("progress_"))
async def mark_task_in_progress(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    user = await UserDAO.get_or_create_user(callback.from_user)

    task = await TaskDAO.mark_status(
        task_id=task_id,
        user_id=user.id,
        status=TaskStatus.IN_PROGRESS
    )

    if task:
        await callback.answer("🔄 Задача в работе!")
        callback.data = f"task_{task_id}"
        await show_task_detail(callback)
    else:
        await callback.answer("Ошибка при обновлении задачи!", show_alert=True)


@router.callback_query(F.data.regexp(r'^edit_\d+$'))
async def start_edit_task(callback: types.CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[1])
    user = await UserDAO.get_or_create_user(callback.from_user)

    task = await TaskDAO.get_task(task_id, user.id)

    if not task:
        await callback.answer("Задача не найдена!", show_alert=True)
        return

    await state.update_data(edit_task_id=task_id)

    await callback.message.edit_text(
        "✏️ <b>Что вы хотите изменить?</b>",
        parse_mode="HTML",
        reply_markup=get_edit_task_keyboard(task_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_title_"))
async def edit_task_title(callback: types.CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[2])
    await state.update_data(edit_task_id=task_id)
    await state.set_state(EditTaskStates.waiting_for_title)

    await callback.message.answer("📝 Введите новое название задачи (до 100 символов):")
    await callback.answer()


@router.callback_query(F.data.startswith("edit_desc_"))
async def edit_task_description(callback: types.CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[2])
    await state.update_data(edit_task_id=task_id)
    await state.set_state(EditTaskStates.waiting_for_description)

    await callback.message.answer("📄 Введите новое описание задачи (до 500 символов):")
    await callback.answer()


@router.callback_query(F.data.startswith("edit_priority_"))
async def edit_task_priority(callback: types.CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[2])
    await state.update_data(edit_task_id=task_id)
    await state.set_state(EditTaskStates.waiting_for_priority)

    await callback.message.answer("🔢 Введите новый приоритет (число от 1 до 10):")
    await callback.answer()


@router.callback_query(F.data.startswith("edit_due_"))
async def edit_task_due_date(callback: types.CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[2])
    await state.update_data(edit_task_id=task_id)
    await state.set_state(EditTaskStates.waiting_for_due_date)

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Удалить срок")],
            [types.KeyboardButton(text="Сегодня"), types.KeyboardButton(text="Завтра")],
            [types.KeyboardButton(text="Через неделю")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await callback.message.answer(
        "📅 Введите новый срок в формате ДД.ММ.ГГГГ\n"
        "Или выберите вариант ниже:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.message(EditTaskStates.waiting_for_title)
async def process_edit_title(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    task_id = data.get('edit_task_id')

    if not task_id:
        await message.answer("Ошибка: не найдена задача для редактирования")
        await state.clear()
        return

    user = await UserDAO.get_or_create_user(message.from_user)

    if len(message.text) > 100:
        await message.answer("Слишком длинное название! Введите до 100 символов:")
        return

    task = await TaskDAO.update_and_get_task(
        task_id=task_id,
        user_id=user.id,
        title=message.text
    )

    if task:
        await message.answer(
            "✅ Название обновлено!",
            reply_markup=get_main_keyboard()
        )
        await send_task_detail(bot, message.chat.id, task_id, user.id)
    else:
        await message.answer("Ошибка при обновлении задачи!")

    await state.clear()


@router.message(EditTaskStates.waiting_for_description)
async def process_edit_description(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    task_id = data.get('edit_task_id')

    if not task_id:
        await message.answer("Ошибка: не найдена задача для редактирования")
        await state.clear()
        return

    user = await UserDAO.get_or_create_user(message.from_user)

    if len(message.text) > 500:
        await message.answer("Слишком длинное описание! Введите до 500 символов:")
        return

    task = await TaskDAO.update_and_get_task(
        task_id=task_id,
        user_id=user.id,
        description=message.text
    )

    if task:
        await message.answer(
            "✅ Описание обновлено!",
            reply_markup=get_main_keyboard()
        )
        await send_task_detail(bot, message.chat.id, task_id, user.id)
    else:
        await message.answer("Ошибка при обновлении задачи!")

    await state.clear()


@router.message(EditTaskStates.waiting_for_priority)
async def process_edit_priority(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    task_id = data.get('edit_task_id')

    if not task_id:
        await message.answer("Ошибка: не найдена задача для редактирования")
        await state.clear()
        return

    user = await UserDAO.get_or_create_user(message.from_user)

    try:
        priority = int(message.text)
        if not 1 <= priority <= 10:
            await message.answer("Введите число от 1 до 10:")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите число от 1 до 10:")
        return

    task = await TaskDAO.update_and_get_task(
        task_id=task_id,
        user_id=user.id,
        priority=priority
    )

    if task:
        await message.answer(
            "✅ Приоритет обновлен!",
            reply_markup=get_main_keyboard()
        )
        await send_task_detail(bot, message.chat.id, task_id, user.id)
    else:
        await message.answer("Ошибка при обновлении задачи!")

    await state.clear()


@router.message(EditTaskStates.waiting_for_due_date)
async def process_edit_due_date(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    task_id = data.get('edit_task_id')

    if not task_id:
        await message.answer("Ошибка: не найдена задача для редактирования")
        await state.clear()
        return

    user = await UserDAO.get_or_create_user(message.from_user)

    due_date = None
    today = datetime.now().date()

    if message.text.lower() == "удалить срок":
        due_date = None
    elif message.text.lower() == "сегодня":
        due_date = today
    elif message.text.lower() == "завтра":
        due_date = today + timedelta(days=1)
    elif message.text.lower() == "через неделю":
        due_date = today + timedelta(days=7)
    else:
        try:
            due_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        except ValueError:
            await message.answer(
                "Неверный формат! Введите дату в формате ДД.ММ.ГГГГ:"
            )
            return

    task = await TaskDAO.update_and_get_task(
        task_id=task_id,
        user_id=user.id,
        due_date=datetime.combine(due_date, datetime.min.time()) if due_date else None
    )

    if task:
        await message.answer(
            "✅ Срок обновлен!",
            reply_markup=get_main_keyboard()
        )
        await send_task_detail(bot, message.chat.id, task_id, user.id)
    else:
        await message.answer("Ошибка при обновлении задачи!")

    await state.clear()


@router.callback_query(F.data.startswith("delete_"))
async def request_delete_task(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[1])

    await callback.message.edit_text(
        "⚠️ <b>Вы уверены, что хотите удалить эту задачу?</b>\n"
        "Это действие нельзя отменить.",
        parse_mode="HTML",
        reply_markup=get_confirmation_keyboard(task_id, "delete")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_task(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[2])
    user = await UserDAO.get_or_create_user(callback.from_user)

    deleted = await TaskDAO.delete_task(task_id, user.id)

    if deleted:
        await callback.message.edit_text("✅ Задача успешно удалена!")
        await callback.answer("Задача удалена!")
    else:
        await callback.message.edit_text("❌ Не удалось удалить задачу!")
        await callback.answer("Ошибка при удалении!", show_alert=True)


@router.callback_query(F.data == "back_to_list")
async def back_to_task_list(callback: types.CallbackQuery, bot: Bot):
    user = await UserDAO.get_or_create_user(callback.from_user)

    tasks = await TaskDAO.get_tasks(
        user_id=user.id,
        limit=TaskDAO.TASKS_PER_PAGE,
        offset=0
    )

    if not tasks:
        await callback.message.answer(
            "📭 У вас пока нет задач.\n"
            "Создайте первую с помощью кнопки '➕ Добавить задачу'",
            reply_markup=get_main_keyboard()
        )
        await callback.answer()
        return

    total_tasks = await TaskDAO.count_tasks(user.id)
    total_pages = (total_tasks + TaskDAO.TASKS_PER_PAGE - 1) // TaskDAO.TASKS_PER_PAGE

    tasks_text = "📋 <b>Ваши задачи:</b>\n\n"
    for i, task in enumerate(tasks, 1):
        status_icons = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅",
            "cancelled": "❌"
        }

        due_text = ""
        if task.due_date:
            task_due_date = task.due_date.date()
            today = datetime.now().date()
            if task_due_date < today and task.status != TaskStatus.COMPLETED:
                due_text = " 🔴"
            elif task_due_date == today:
                due_text = " ⚠️"
            else:
                due_text = f" 📅 {task.due_date.strftime('%d.%m')}"

        tasks_text += (
            f"{i}. {status_icons.get(task.status, '📝')} "
            f"<b>{task.title}</b>{due_text}\n"
            f"   Приоритет: {task.priority}/10\n\n"
        )

    tasks_text += f"\nСтраница 1/{total_pages}"

    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=tasks_text,
        parse_mode="HTML",
        reply_markup=get_tasks_keyboard(tasks, page=0, total_pages=total_pages)
    )
    await callback.answer()


async def send_task_detail(bot: Bot, chat_id: int, task_id: int, user_id: int):
    """Вспомогательная функция для отображения деталей задачи"""
    task = await TaskDAO.get_task(task_id, user_id)

    if not task:
        await bot.send_message(chat_id, "❌ Задача не найдена!")
        return

    status_display = {
        "pending": "⏳ Ожидает",
        "in_progress": "🔄 В работе",
        "completed": "✅ Выполнена",
        "cancelled": "❌ Отменена"
    }.get(task.status, task.status)

    priority_stars = "⭐" * min(task.priority, 5)

    task_text = (
        f"📋 <b>Детали задачи</b>\n\n"
        f"<b>Название:</b> {task.title}\n"
        f"<b>Описание:</b>\n{task.description}\n\n"
        f"<b>Статус:</b> {status_display}\n"
        f"<b>Приоритет:</b> {priority_stars} ({task.priority}/10)\n"
        f"<b>Создана:</b> {task.created_at.strftime('%d.%m.%Y %H:%M')}\n"
    )

    if task.due_date:
        due_date_str = task.due_date.strftime('%d.%m.%Y')
        task_due_date = task.due_date.date()
        today = datetime.now().date()
        if task_due_date < today and task.status != TaskStatus.COMPLETED:
            due_date_str += " 🔴 Просрочена!"
        elif task_due_date == today:
            due_date_str += " ⚠️ Сегодня!"
        task_text += f"<b>Срок:</b> {due_date_str}\n"

    if task.completed_at:
        task_text += f"<b>Завершена:</b> {task.completed_at.strftime('%d.%m.%Y %H:%M')}\n"

    await bot.send_message(
        chat_id=chat_id,
        text=task_text,
        parse_mode="HTML",
        reply_markup=get_task_detail_keyboard(task_id)
    )