from aiogram import Router, types
from aiogram.filters import Command
from datetime import datetime
from app.database.dao.task import TaskDAO
from app.database.dao.user import UserDAO
from app.keyboards.inline import get_tasks_keyboard
from app.keyboards.reply import get_main_keyboard

router = Router()


@router.message(Command("tasks"))
async def cmd_tasks(message: types.Message):
    await show_tasks_page(message, page=0)


# Хендлер для кнопки "Мои задачи"
@router.message(lambda message: message.text == "📋 Мои задачи")
async def tasks_button(message: types.Message):
    await cmd_tasks(message)


# В функции show_tasks_page:
async def show_tasks_page(message: types.Message, page: int = 0):
    # Получаем пользователя из базы данных
    user = await UserDAO.get_or_create_user(message.from_user)

    # Получаем задачи с пагинацией
    tasks = await TaskDAO.get_tasks(
        user_id=user.id,
        limit=TaskDAO.TASKS_PER_PAGE,
        offset=page * TaskDAO.TASKS_PER_PAGE
    )

    if not tasks:
        await message.answer(
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

        # Берем первую иконку из статуса
        icon = status_icons.get(task.status, "📝")

        due_text = ""
        if task.due_date:
            task_due_date = task.due_date.date()
            today = datetime.now().date()
            if task_due_date < today and task.status != "completed":
                due_text = " 🔴 Просрочена!"
            else:
                due_text = f" 📅 {task.due_date.strftime('%d.%m.%Y')}"

        tasks_text += (
            f"{i}. {icon} "
            f"<b>{task.title}</b>\n"
            f"   Приоритет: {task.priority}{due_text}\n\n"
        )

    tasks_text += f"\nСтраница {page + 1}/{total_pages}"

    await message.answer(
        tasks_text,
        parse_mode="HTML",
        reply_markup=get_tasks_keyboard(tasks, page=page, total_pages=total_pages)
    )