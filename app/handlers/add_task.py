from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta

from app.database.dao.task import TaskDAO
from app.database.dao.user import UserDAO
from app.database.dao.gamification import GamificationDAO
from app.constants.gamification import ACHIEVEMENTS
from app.keyboards.reply import get_main_keyboard

router = Router()


class AddTaskStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_priority = State()
    waiting_for_due_date = State()


@router.message(Command("add"))
async def cmd_add_task(message: types.Message, state: FSMContext):
    await message.answer(
        "📝 Введите название задачи (до 100 символов):"
    )
    await state.set_state(AddTaskStates.waiting_for_title)


@router.message(lambda message: message.text == "➕ Добавить задачу")
async def add_task_button(message: types.Message, state: FSMContext):
    await cmd_add_task(message, state)


@router.message(AddTaskStates.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    if len(message.text) > 100:
        await message.answer("Слишком длинное название! Введите до 100 символов:")
        return

    await state.update_data(title=message.text)
    await message.answer(
        "📄 Введите описание задачи (до 500 символов):"
    )
    await state.set_state(AddTaskStates.waiting_for_description)


@router.message(AddTaskStates.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    if len(message.text) > 500:
        await message.answer("Слишком длинное описание! Введите до 500 символов:")
        return

    await state.update_data(description=message.text)
    await message.answer(
        "🔢 Введите приоритет задачи (число от 1 до 10, где 10 - наивысший):"
    )
    await state.set_state(AddTaskStates.waiting_for_priority)


@router.message(AddTaskStates.waiting_for_priority)
async def process_priority(message: types.Message, state: FSMContext):
    try:
        priority = int(message.text)
        if not 1 <= priority <= 10:
            await message.answer("Введите число от 1 до 10:")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите число от 1 до 10:")
        return

    await state.update_data(priority=priority)

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Пропустить")],
            [types.KeyboardButton(text="Сегодня")],
            [types.KeyboardButton(text="Завтра")],
            [types.KeyboardButton(text="Через неделю")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await message.answer(
        "📅 Введите срок выполнения в формате ДД.ММ.ГГГГ "
        "или выберите вариант ниже:\n"
        "Пример: 31.12.2024",
        reply_markup=keyboard
    )
    await state.set_state(AddTaskStates.waiting_for_due_date)


@router.message(AddTaskStates.waiting_for_due_date)
async def process_due_date(message: types.Message, state: FSMContext):
    due_date = None
    today = datetime.now().date()

    if message.text.lower() == "пропустить":
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
                "Неверный формат! Введите дату в формате ДД.ММ.ГГГГ\n"
                "Пример: 31.12.2024"
            )
            return

    await state.update_data(due_date=due_date)

    # Получаем данные из состояния
    data = await state.get_data()

    # Получаем или создаем пользователя в базе данных
    db_user = await UserDAO.get_or_create_user(message.from_user)

    # Создаем задачу
    task = await TaskDAO.create_and_get_task(
        user_id=db_user.id,
        title=data['title'],
        description=data['description'],
        priority=data.get('priority', 1),
        due_date=datetime.combine(data['due_date'], datetime.min.time()) if data['due_date'] else None
    )

    # === ГЕЙМИФИКАЦИЯ ===

    # Увеличиваем счётчик созданных задач
    await GamificationDAO.increment_created(db_user.id)

    # Проверяем достижения
    new_achievements = await GamificationDAO.check_and_unlock_achievements(db_user.id)

    # Формируем текст достижений
    achievement_text = ""
    total_bonus_xp = 0

    if new_achievements:
        achievement_text = "\n\n🏆 <b>Новые достижения:</b>"
        for ach_id in new_achievements:
            ach = ACHIEVEMENTS.get(ach_id)
            if ach:
                achievement_text += f"\n{ach.icon} <b>{ach.name}</b>"
                if ach.xp_reward > 0:
                    achievement_text += f" (+{ach.xp_reward} XP)"
                    total_bonus_xp += ach.xp_reward

        # Добавляем бонусный XP за достижения
        if total_bonus_xp > 0:
            await GamificationDAO.add_xp(db_user.id, total_bonus_xp)

    # Форматируем статус для красивого отображения
    status_display = {
        "pending": "⏳ Ожидает",
        "in_progress": "🔄 В работе",
        "completed": "✅ Выполнена"
    }.get(task.status, task.status)

    await message.answer(
        f"✅ <b>Задача создана!</b>\n\n"
        f"<b>Название:</b> {task.title}\n"
        f"<b>Описание:</b> {task.description}\n"
        f"<b>Приоритет:</b> {'⭐' * min(task.priority, 5)} ({task.priority}/10)\n"
        f"<b>Срок:</b> {task.due_date.strftime('%d.%m.%Y') if task.due_date else 'Не установлен'}\n"
        f"<b>Статус:</b> {status_display}"
        f"{achievement_text}",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

    await state.clear()