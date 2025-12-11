from aiogram import Router, types, F
from aiogram.filters import Command
from datetime import datetime

from app.database.dao.user import UserDAO
from app.database.dao.gamification import GamificationDAO
from app.constants.gamification import (
    ACHIEVEMENTS,
    get_xp_for_level,
    get_level_emoji,
    get_title,
)
from app.keyboards.reply import get_main_keyboard

router = Router()


def create_progress_bar(current: int, maximum: int, length: int = 10) -> str:
    """Создаёт прогресс-бар"""
    filled = int((current / maximum) * length) if maximum > 0 else 0
    empty = length - filled
    return "█" * filled + "░" * empty


@router.message(Command("profile"))
@router.message(lambda m: m.text == "👤 Профиль")
async def cmd_profile(message: types.Message):
    user = await UserDAO.get_or_create_user(message.from_user)
    stats = await GamificationDAO.get_user_stats(user.id)

    if not stats:
        await message.answer("Ошибка при получении профиля")
        return

    level = stats["level"]
    xp = stats["xp"]
    xp_next = stats["xp_for_next_level"]
    xp_current_level = get_xp_for_level(level)
    xp_progress = xp - xp_current_level
    xp_needed = xp_next - xp_current_level

    level_emoji = get_level_emoji(level)
    title = get_title(level)
    progress_bar = create_progress_bar(xp_progress, xp_needed, 15)

    # Формируем сообщение профиля
    profile_text = (
        f"👤 <b>Профиль</b>\n\n"
        f"{level_emoji} <b>Уровень {level}</b> — {title}\n"
        f"├ XP: {xp} / {xp_next}\n"
        f"└ [{progress_bar}]\n\n"

        f"🔥 <b>Стрик:</b> {stats['current_streak']} дн.\n"
        f"🏆 <b>Лучший стрик:</b> {stats['max_streak']} дн.\n\n"

        f"📊 <b>Статистика задач:</b>\n"
        f"├ ✅ Выполнено: {stats['total_completed']}\n"
        f"├ 📝 Создано: {stats['total_created']}\n"
        f"└ ⚡ Сегодня: {stats['tasks_today']}\n\n"

        f"🏅 <b>Достижения:</b> {stats['achievements_count']}/{stats['total_achievements']}"
    )

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="🏅 Достижения", callback_data="show_achievements"),
            types.InlineKeyboardButton(text="📈 Лидерборд", callback_data="show_leaderboard")
        ],
        [
            types.InlineKeyboardButton(text="📊 Подробная статистика", callback_data="detailed_stats")
        ]
    ])

    await message.answer(profile_text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "show_achievements")
async def show_achievements(callback: types.CallbackQuery):
    user = await UserDAO.get_or_create_user(callback.from_user)
    user_achievements = await GamificationDAO.get_user_achievements(user.id)

    text_parts = ["🏅 <b>Достижения</b>\n"]

    # Разблокированные
    unlocked = []
    locked = []

    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in user_achievements:
            unlocked.append(f"{ach.icon} <b>{ach.name}</b>\n   └ {ach.description}")
        else:
            locked.append(f"🔒 <b>{ach.name}</b>\n   └ {ach.description}")

    if unlocked:
        text_parts.append(f"\n✅ <b>Получено ({len(unlocked)}):</b>\n")
        text_parts.extend(unlocked[:10])  # Показываем первые 10
        if len(unlocked) > 10:
            text_parts.append(f"\n...и ещё {len(unlocked) - 10}")

    if locked:
        text_parts.append(f"\n\n🔒 <b>Заблокировано ({len(locked)}):</b>\n")
        text_parts.extend(locked[:5])  # Показываем первые 5 заблокированных
        if len(locked) > 5:
            text_parts.append(f"\n...и ещё {len(locked) - 5}")

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_profile")]
    ])

    await callback.message.edit_text(
        "\n".join(text_parts),
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "show_leaderboard")
async def show_leaderboard(callback: types.CallbackQuery):
    user = await UserDAO.get_or_create_user(callback.from_user)
    leaderboard = await GamificationDAO.get_leaderboard(10)

    text_parts = ["📈 <b>Лидерборд</b>\n\n"]

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    for leader, position in leaderboard:
        medal = medals.get(position, f"{position}.")
        is_you = " ← Вы" if leader.id == user.id else ""
        username = leader.username or f"User {leader.tg_id}"
        level_emoji = get_level_emoji(leader.level)

        text_parts.append(
            f"{medal} <b>{username}</b>{is_you}\n"
            f"   {level_emoji} Ур. {leader.level} • {leader.xp} XP • 🔥 {leader.current_streak}\n"
        )

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_profile")]
    ])

    await callback.message.edit_text(
        "".join(text_parts),
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "detailed_stats")
async def show_detailed_stats(callback: types.CallbackQuery):
    user = await UserDAO.get_or_create_user(callback.from_user)
    stats = await GamificationDAO.get_user_stats(user.id)

    status_counts = stats.get("status_counts", {})
    pending = status_counts.get("pending", 0)
    in_progress = status_counts.get("in_progress", 0)
    completed = status_counts.get("completed", 0)
    cancelled = status_counts.get("cancelled", 0)

    total = pending + in_progress + completed + cancelled
    completion_rate = (completed / total * 100) if total > 0 else 0

    text = (
        f"📊 <b>Подробная статистика</b>\n\n"

        f"📋 <b>Задачи по статусам:</b>\n"
        f"├ ⏳ Ожидают: {pending}\n"
        f"├ 🔄 В работе: {in_progress}\n"
        f"├ ✅ Выполнено: {completed}\n"
        f"└ ❌ Отменено: {cancelled}\n\n"

        f"📈 <b>Эффективность:</b>\n"
        f"├ Всего задач: {total}\n"
        f"├ Процент выполнения: {completion_rate:.1f}%\n"
        f"└ В среднем за день: ~{stats['total_completed'] / max(stats['max_streak'], 1):.1f}\n\n"

        f"🔥 <b>Стрики:</b>\n"
        f"├ Текущий: {stats['current_streak']} дней\n"
        f"└ Рекорд: {stats['max_streak']} дней\n\n"

        f"⭐ <b>Прогресс:</b>\n"
        f"├ Всего XP: {stats['xp']}\n"
        f"├ Уровень: {stats['level']}\n"
        f"└ Достижений: {stats['achievements_count']}/{stats['total_achievements']}"
    )

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_profile")]
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: types.CallbackQuery):
    user = await UserDAO.get_or_create_user(callback.from_user)
    stats = await GamificationDAO.get_user_stats(user.id)

    level = stats["level"]
    xp = stats["xp"]
    xp_next = stats["xp_for_next_level"]
    xp_current_level = get_xp_for_level(level)
    xp_progress = xp - xp_current_level
    xp_needed = xp_next - xp_current_level

    level_emoji = get_level_emoji(level)
    title = get_title(level)
    progress_bar = create_progress_bar(xp_progress, xp_needed, 15)

    profile_text = (
        f"👤 <b>Профиль</b>\n\n"
        f"{level_emoji} <b>Уровень {level}</b> — {title}\n"
        f"├ XP: {xp} / {xp_next}\n"
        f"└ [{progress_bar}]\n\n"

        f"🔥 <b>Стрик:</b> {stats['current_streak']} дн.\n"
        f"🏆 <b>Лучший стрик:</b> {stats['max_streak']} дн.\n\n"

        f"📊 <b>Статистика задач:</b>\n"
        f"├ ✅ Выполнено: {stats['total_completed']}\n"
        f"├ 📝 Создано: {stats['total_created']}\n"
        f"└ ⚡ Сегодня: {stats['tasks_today']}\n\n"

        f"🏅 <b>Достижения:</b> {stats['achievements_count']}/{stats['total_achievements']}"
    )

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="🏅 Достижения", callback_data="show_achievements"),
            types.InlineKeyboardButton(text="📈 Лидерборд", callback_data="show_leaderboard")
        ],
        [
            types.InlineKeyboardButton(text="📊 Подробная статистика", callback_data="detailed_stats")
        ]
    ])

    await callback.message.edit_text(profile_text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

    # Обновляем обработчик выполнения задачи
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
        is_on_time = task.due_date and datetime.utcnow() <= task.due_date
        is_same_day = task.created_at.date() == datetime.now().date()
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
        message_parts.append(f"\n\n✅ <b>{task.title}</b> выполнена!")
        message_parts.append(f"\n💫 +{xp_earned} XP")

        # Сообщение о повышении уровня
        if leveled_up:
            level_emoji = get_level_emoji(new_level)
            message_parts.append(f"\n\n🎉 <b>УРОВЕНЬ {new_level}!</b> {level_emoji}")

        # Сообщение о стрике
        if streak_lost:
            message_parts.append(f"\n\n{get_random_streak_lost_phrase()}")
        else:
            streak_phrase = get_streak_phrase(new_streak)
            if streak_phrase:
                message_parts.append(f"\n\n{streak_phrase}")
            elif new_streak > 1:
                message_parts.append(f"\n\n🔥 Стрик: {new_streak} дней!")

        # Сообщение о новых достижениях
        if new_achievements:
            message_parts.append("\n\n🏆 <b>Новые достижения:</b>")
            for ach_id in new_achievements:
                ach = ACHIEVEMENTS.get(ach_id)
                if ach:
                    message_parts.append(f"\n{ach.icon} <b>{ach.name}</b> (+{ach.xp_reward} XP)")
                    # Добавляем XP за достижение
                    await GamificationDAO.add_xp(user.id, ach.xp_reward)

        # Отправляем сообщение
        await callback.message.answer(
            "".join(message_parts),
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

        # Обновляем детали задачи
        await show_task_detail(callback)
        await callback.answer("✅ Задача выполнена!")
