from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from app.database.dao.task import TaskDAO
from app.database.dao.user import UserDAO
from app.database.enums import TaskStatus
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


# Обработка нажатия на задачу в списке
@router.callback_query(F.data.startswith("task_"))
async def show_task_detail(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    user = await UserDAO.get_or_create_user(callback.from_user)

    task = await TaskDAO.get_task(task_id, user.id)

    if not task:
        await callback.answer("Задача не найдена!", show_alert=True)
        return

    # Форматируем статус для красивого отображения
    status_display = {
        "pending": "⏳ Ожидает",
        "in_progress": "🔄 В работе",
        "completed": "✅ Выполнена"
    }.get(task.status, task.status)

    task_text = (
        f"{status_display[0]} <b>Детали задачи</b>\n\n"
        f"<b>Название:</b> {task.title}\n"
        f"<b>Описание:</b>\n{task.description}\n\n"
        f"<b>Статус:</b> {status_display}\n"
        f"<b>Приоритет:</b> {task.priority}\n"
        f"<b>Создана:</b> {task.created_at.strftime('%d.%m.%Y %H:%M')}\n"
    )

    if task.due_date:
        due_date_str = task.due_date.strftime('%d.%m.%Y')
        task_due_date = task.due_date.date()
        today = datetime.now().date()
        if task_due_date < today and task.status != "completed":
            due_date_str += " 🔴 Просрочена!"
        task_text += f"<b>Срок:</b> {due_date_str}\n"

    if task.completed_at:
        task_text += f"<b>Завершена:</b> {task.completed_at.strftime('%d.%m.%Y %H:%M')}\n"

    await callback.message.edit_text(
        task_text,
        parse_mode="HTML",
        reply_markup=get_task_detail_keyboard(task_id)
    )
    await callback.answer()


# Обработка пагинации
@router.callback_query(F.data.startswith("page_"))
async def handle_pagination(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[1])
    user = await UserDAO.get_or_create_user(callback.from_user)

    # Получаем задачи для страницы
    tasks = await TaskDAO.get_tasks(
        user_id=user.id,
        limit=TaskDAO.TASKS_PER_PAGE,
        offset=page * TaskDAO.TASKS_PER_PAGE
    )

    if not tasks:
        await callback.answer("Больше нет задач!", show_alert=True)
        return

    # Вычисляем общее количество страниц
    total_tasks = await TaskDAO.count_tasks(user.id)
    total_pages = (total_tasks + TaskDAO.TASKS_PER_PAGE - 1) // TaskDAO.TASKS_PER_PAGE

    tasks_text = "📋 <b>Ваши задачи:</b>\n\n"
    for i, task in enumerate(tasks, 1):
        status_icons = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅"
        }

        due_text = ""
        if task.due_date:
            task_due_date = task.due_date.date()
            today = datetime.now().date()
            if task_due_date < today and task.status != "completed":
                due_text = " 🔴 Просрочена!"
            else:
                due_text = f" 📅 {task.due_date.strftime('%d.%m.%Y')}"

        tasks_text += (
            f"{i}. {status_icons.get(task.status, '📝')} "
            f"<b>{task.title}</b>\n"
            f"   Приоритет: {task.priority}{due_text}\n\n"
        )

    tasks_text += f"\nСтраница {page + 1}/{total_pages}"

    await callback.message.edit_text(
        tasks_text,
        parse_mode="HTML",
        reply_markup=get_tasks_keyboard(tasks, page=page, total_pages=total_pages)
    )
    await callback.answer()


# Отметить задачу выполненной
@router.callback_query(F.data.startswith("done_"))
async def mark_task_done(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    user = await UserDAO.get_or_create_user(callback.from_user)

    task = await TaskDAO.mark_status(
        task_id=task_id,
        user_id=user.id,
        status=TaskStatus.COMPLETED
    )

    if task:
        await callback.answer("✅ Задача отмечена как выполненная!")
        await show_task_detail(callback)
    else:
        await callback.answer("Ошибка при обновлении задачи!", show_alert=True)


# Отметить задачу в работе
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
        await show_task_detail(callback)
    else:
        await callback.answer("Ошибка при обновлении задачи!", show_alert=True)


# Начать редактирование задачи - только для callback_data вида "edit_{task_id}"
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


# Редактирование названия задачи - для callback_data вида "edit_title_{task_id}"
@router.callback_query(F.data.startswith("edit_title_"))
async def edit_task_title(callback: types.CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[2])  # Берем третий элемент
    await state.update_data(edit_task_id=task_id)
    await state.set_state(EditTaskStates.waiting_for_title)

    # Отправляем новое сообщение для ввода названия
    await callback.message.answer("📝 Введите новое название задачи (до 100 символов):")
    await callback.answer()


# Редактирование описания задачи - для callback_data вида "edit_desc_{task_id}"
@router.callback_query(F.data.startswith("edit_desc_"))
async def edit_task_description(callback: types.CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[2])  # Берем третий элемент
    await state.update_data(edit_task_id=task_id)
    await state.set_state(EditTaskStates.waiting_for_description)

    await callback.message.answer("📄 Введите новое описание задачи (до 500 символов):")
    await callback.answer()


# Редактирование приоритета задачи - для callback_data вида "edit_priority_{task_id}"
@router.callback_query(F.data.startswith("edit_priority_"))
async def edit_task_priority(callback: types.CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[2])  # Берем третий элемент
    await state.update_data(edit_task_id=task_id)
    await state.set_state(EditTaskStates.waiting_for_priority)

    await callback.message.answer("🔢 Введите новый приоритет (число от 1 до 10):")
    await callback.answer()


# Редактирование срока задачи - для callback_data вида "edit_due_{task_id}"
@router.callback_query(F.data.startswith("edit_due_"))
async def edit_task_due_date(callback: types.CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[2])  # Берем третий элемент
    await state.update_data(edit_task_id=task_id)
    await state.set_state(EditTaskStates.waiting_for_due_date)

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Удалить срок")],
            [types.KeyboardButton(text="Сегодня")],
            [types.KeyboardButton(text="Завтра")]
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


# Обработка ввода нового названия
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
        # Отправляем детали задачи
        await send_task_detail(bot, message.chat.id, task_id, user.id)
    else:
        await message.answer("Ошибка при обновлении задачи!")

    await state.clear()


# Обработка ввода нового описания
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


# Обработка ввода нового приоритета
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


# Обработка ввода новой даты
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

    if message.text.lower() == "удалить срок":
        due_date = None
    elif message.text.lower() == "сегодня":
        due_date = datetime.now().date()
    elif message.text.lower() == "завтра":
        due_date = datetime.now().date().replace(day=datetime.now().day + 1)
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


# Запрос на удаление задачи
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


# Подтверждение удаления
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


# Возврат к списку задач
@router.callback_query(F.data == "back_to_list")
async def back_to_task_list(callback: types.CallbackQuery, bot: Bot):
    user = await UserDAO.get_or_create_user(callback.from_user)

    # Получаем задачи с пагинацией
    tasks = await TaskDAO.get_tasks(
        user_id=user.id,
        limit=TaskDAO.TASKS_PER_PAGE,
        offset=0
    )

    if not tasks:
        await callback.message.answer(
            "📭 У вас пока нет задач. Создайте первую с помощью кнопки '➕ Добавить задачу'",
            reply_markup=get_main_keyboard()
        )
        return

    # Вычисляем общее количество страниц
    total_tasks = await TaskDAO.count_tasks(user.id)
    total_pages = (total_tasks + TaskDAO.TASKS_PER_PAGE - 1) // TaskDAO.TASKS_PER_PAGE

    tasks_text = "📋 <b>Ваши задачи:</b>\n\n"
    for i, task in enumerate(tasks, 1):
        status_icons = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅"
        }

        due_text = ""
        if task.due_date:
            task_due_date = task.due_date.date()
            today = datetime.now().date()
            if task_due_date < today and task.status != "completed":
                due_text = " 🔴 Просрочена!"
            else:
                due_text = f" 📅 {task.due_date.strftime('%d.%m.%Y')}"

        tasks_text += (
            f"{i}. {status_icons.get(task.status, '📝')} "
            f"<b>{task.title}</b>\n"
            f"   Приоритет: {task.priority}{due_text}\n\n"
        )

    tasks_text += f"\nСтраница 1/{total_pages}"

    # Отправляем новое сообщение со списком задач
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=tasks_text,
        parse_mode="HTML",
        reply_markup=get_tasks_keyboard(tasks, page=0, total_pages=total_pages)
    )
    await callback.answer()

# Вспомогательная функция для отправки деталей задачи
async def send_task_detail(bot: Bot, chat_id: int, task_id: int, user_id: int):
    """Вспомогательная функция для отображения деталей задачи"""
    task = await TaskDAO.get_task(task_id, user_id)

    if not task:
        await bot.send_message(chat_id, "❌ Задача не найдена!")
        return

    status_icons = {
        "pending": "⏳",
        "in_progress": "🔄",
        "completed": "✅"
    }

    task_text = (
        f"{status_icons.get(task.status, '📝')} <b>Детали задачи</b>\n\n"
        f"<b>Название:</b> {task.title}\n"
        f"<b>Описание:</b>\n{task.description}\n\n"
        f"<b>Статус:</b> {task.status.replace('_', ' ').title()}\n"
        f"<b>Приоритет:</b> {task.priority}\n"
        f"<b>Создана:</b> {task.created_at.strftime('%d.%m.%Y %H:%M')}\n"
    )

    if task.due_date:
        task_text += f"<b>Срок:</b> {task.due_date.strftime('%d.%m.%Y')}\n"

    if task.completed_at:
        task_text += f"<b>Завершена:</b> {task.completed_at.strftime('%d.%m.%Y %H:%M')}\n"

    await bot.send_message(
        chat_id=chat_id,
        text=task_text,
        parse_mode="HTML",
        reply_markup=get_task_detail_keyboard(task_id)
    )