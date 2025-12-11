import logging
from datetime import datetime
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.database.dao.reminder import ReminderDAO
from app.database.dao.gamification import GamificationDAO
from app.database.enums import TaskStatus
from app.constants.gamification import (
    get_random_morning_phrase,
    get_level_emoji,
)

logger = logging.getLogger(__name__)


def get_task_reminder_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для напоминания"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выполнено", callback_data=f"done_{task_id}"),
            InlineKeyboardButton(text="👁 Открыть", callback_data=f"task_{task_id}")
        ]
    ])


async def check_upcoming_deadlines(bot: Bot):
    """Проверка приближающихся дедлайнов и отправка напоминаний"""
    logger.info("Checking upcoming deadlines...")

    try:
        tasks_with_users = await ReminderDAO.get_tasks_for_reminder()

        for task, user in tasks_with_users:
            try:
                time_left = task.due_date - datetime.utcnow()
                hours_left = int(time_left.total_seconds() // 3600)

                if hours_left <= 0:
                    time_text = "менее часа"
                elif hours_left == 1:
                    time_text = "1 час"
                elif 2 <= hours_left <= 4:
                    time_text = f"{hours_left} часа"
                else:
                    time_text = f"{hours_left} часов"

                priority_stars = "⭐" * min(task.priority, 5)

                message_text = (
                    f"⏰ <b>Напоминание о задаче!</b>\n\n"
                    f"📝 <b>{task.title}</b>\n\n"
                    f"⏳ До дедлайна осталось: <b>{time_text}</b>\n"
                    f"📅 Срок: {task.due_date.strftime('%d.%m.%Y %H:%M')}\n"
                    f"🎯 Приоритет: {priority_stars} ({task.priority}/10)\n\n"
                    f"💪 Не откладывай на потом!"
                )

                await bot.send_message(
                    chat_id=user.tg_id,
                    text=message_text,
                    parse_mode="HTML",
                    reply_markup=get_task_reminder_keyboard(task.id)
                )

                await ReminderDAO.mark_reminder_sent(task.id)
                logger.info(f"Sent deadline reminder for task {task.id} to user {user.tg_id}")

            except Exception as e:
                logger.error(f"Error sending reminder for task {task.id}: {e}")

    except Exception as e:
        logger.error(f"Error in check_upcoming_deadlines: {e}")


async def check_overdue_tasks(bot: Bot):
    """Проверка просроченных задач"""
    logger.info("Checking overdue tasks...")

    try:
        tasks_with_users = await ReminderDAO.get_overdue_tasks()

        for task, user in tasks_with_users:
            try:
                overdue_time = datetime.utcnow() - task.due_date
                days_overdue = overdue_time.days
                hours_overdue = int(overdue_time.total_seconds() // 3600) % 24

                if days_overdue == 0:
                    if hours_overdue == 1:
                        time_text = "1 час назад"
                    elif 2 <= hours_overdue <= 4:
                        time_text = f"{hours_overdue} часа назад"
                    else:
                        time_text = f"{hours_overdue} часов назад"
                elif days_overdue == 1:
                    time_text = "вчера"
                elif 2 <= days_overdue <= 4:
                    time_text = f"{days_overdue} дня назад"
                else:
                    time_text = f"{days_overdue} дней назад"

                message_text = (
                    f"🔴 <b>Задача просрочена!</b>\n\n"
                    f"📝 <b>{task.title}</b>\n\n"
                    f"📅 Срок был: {task.due_date.strftime('%d.%m.%Y')}\n"
                    f"⏰ Просрочена: {time_text}\n"
                    f"🎯 Приоритет: {task.priority}/10\n\n"
                    f"⚡ Не забудь выполнить или обновить срок!"
                )

                await bot.send_message(
                    chat_id=user.tg_id,
                    text=message_text,
                    parse_mode="HTML",
                    reply_markup=get_task_reminder_keyboard(task.id)
                )

                await ReminderDAO.mark_overdue_reminder_sent(task.id)
                logger.info(f"Sent overdue reminder for task {task.id} to user {user.tg_id}")

            except Exception as e:
                logger.error(f"Error sending overdue reminder for task {task.id}: {e}")

    except Exception as e:
        logger.error(f"Error in check_overdue_tasks: {e}")


async def send_daily_summary(bot: Bot):
    """Отправка утренней сводки задач с мотивацией"""
    logger.info("Sending daily summaries...")

    try:
        users_with_tasks = await ReminderDAO.get_daily_summary()

        for user, tasks in users_with_tasks:
            try:
                # Получаем статистику пользователя
                stats = await GamificationDAO.get_user_stats(user.id)

                # Разделяем на категории
                overdue_tasks = []
                today_tasks = []
                upcoming_tasks = []
                in_progress_tasks = []

                now = datetime.utcnow()
                today = now.date()

                for task in tasks:
                    if task.status == TaskStatus.IN_PROGRESS:
                        in_progress_tasks.append(task)

                    if task.due_date:
                        task_date = task.due_date.date()
                        if task_date < today:
                            overdue_tasks.append(task)
                        elif task_date == today:
                            today_tasks.append(task)
                        else:
                            upcoming_tasks.append(task)
                    else:
                        upcoming_tasks.append(task)

                # Мотивационное приветствие
                greeting = get_random_morning_phrase()
                level = stats.get('level', 1)
                level_emoji = get_level_emoji(level)
                streak = stats.get('current_streak', 0)

                message_parts = [
                    greeting,
                    f"\n\n{level_emoji} <b>Уровень {level}</b>"
                ]

                # Добавляем информацию о стрике
                if streak > 0:
                    message_parts.append(f" | 🔥 Стрик: {streak} дн.")

                # Задачи в работе
                if in_progress_tasks:
                    message_parts.append(f"\n\n🔄 <b>В работе ({len(in_progress_tasks)}):</b>")
                    for task in in_progress_tasks[:3]:
                        message_parts.append(f"\n• {task.title}")
                    if len(in_progress_tasks) > 3:
                        message_parts.append(f"\n  <i>...и ещё {len(in_progress_tasks) - 3}</i>")

                # Просроченные задачи
                if overdue_tasks:
                    message_parts.append(f"\n\n🔴 <b>Просрочено ({len(overdue_tasks)}):</b>")
                    for task in overdue_tasks[:3]:
                        days = (today - task.due_date.date()).days
                        message_parts.append(f"\n• {task.title} (-{days} дн.)")
                    if len(overdue_tasks) > 3:
                        message_parts.append(f"\n  <i>...и ещё {len(overdue_tasks) - 3}</i>")

                # Задачи на сегодня
                if today_tasks:
                    message_parts.append(f"\n\n📅 <b>На сегодня ({len(today_tasks)}):</b>")
                    for task in today_tasks[:5]:
                        priority_indicator = "❗" if task.priority >= 8 else ""
                        message_parts.append(f"\n• {task.title} {priority_indicator}")
                    if len(today_tasks) > 5:
                        message_parts.append(f"\n  <i>...и ещё {len(today_tasks) - 5}</i>")

                # Предстоящие задачи
                if upcoming_tasks and not today_tasks:
                    message_parts.append(f"\n\n📋 <b>Предстоящие:</b>")
                    for task in upcoming_tasks[:3]:
                        due_text = ""
                        if task.due_date:
                            due_text = f" (до {task.due_date.strftime('%d.%m')})"
                        message_parts.append(f"\n• {task.title}{due_text}")

                # Статистика
                total_active = len(overdue_tasks) + len(today_tasks) + len(upcoming_tasks)
                completed_total = stats.get('total_completed', 0)

                message_parts.append(
                    f"\n\n📊 <b>Статистика:</b>\n"
                    f"├ Активных задач: {total_active}\n"
                    f"├ Выполнено всего: {completed_total}\n"
                    f"└ Сегодня выполнено: {stats.get('tasks_today', 0)}"
                )

                # Мотивация в зависимости от ситуации
                if overdue_tasks:
                    message_parts.append(
                        f"\n\n⚡ <b>Совет дня:</b> Начни с просроченных задач!"
                    )
                elif today_tasks:
                    message_parts.append(
                        f"\n\n💪 <b>Совет дня:</b> У тебя {len(today_tasks)} задач на сегодня. Ты справишься!"
                    )
                elif streak >= 7:
                    message_parts.append(
                        f"\n\n🔥 <b>Отлично!</b> Твой стрик — {streak} дней! Продолжай в том же духе!"
                    )
                elif streak == 0:
                    message_parts.append(
                        f"\n\n🌟 <b>Совет дня:</b> Выполни хотя бы одну задачу и начни новый стрик!"
                    )
                else:
                    message_parts.append(
                        f"\n\n✨ <b>Отличного дня!</b> Пусть всё получится!"
                    )

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📋 Мои задачи", callback_data="back_to_list"),
                        InlineKeyboardButton(text="➕ Добавить", callback_data="add_task_inline")
                    ],
                    [
                        InlineKeyboardButton(text="👤 Профиль", callback_data="back_to_profile")
                    ]
                ])

                await bot.send_message(
                    chat_id=user.tg_id,
                    text="".join(message_parts),
                    parse_mode="HTML",
                    reply_markup=keyboard
                )

                logger.info(f"Sent daily summary to user {user.tg_id}")

            except Exception as e:
                logger.error(f"Error sending daily summary to user {user.tg_id}: {e}")

    except Exception as e:
        logger.error(f"Error in send_daily_summary: {e}")


async def check_streak_reminder(bot: Bot):
    """
    Напоминание о стрике в конце дня (если пользователь ещё не выполнил задачу)
    """
    logger.info("Checking streak reminders...")

    try:
        users_at_risk = await ReminderDAO.get_users_with_streak_at_risk()

        for user in users_at_risk:
            try:
                if user.current_streak >= 3:
                    message_text = (
                        f"⚠️ <b>Внимание! Стрик под угрозой!</b>\n\n"
                        f"🔥 Твой текущий стрик: <b>{user.current_streak} дней</b>\n\n"
                        f"Сегодня ты ещё не выполнил ни одной задачи.\n"
                        f"Не дай стрику прерваться!\n\n"
                        f"💪 Осталось совсем немного времени до конца дня!"
                    )

                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="📋 Мои задачи", callback_data="back_to_list")
                        ]
                    ])

                    await bot.send_message(
                        chat_id=user.tg_id,
                        text=message_text,
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )

                    logger.info(f"Sent streak reminder to user {user.tg_id}")

            except Exception as e:
                logger.error(f"Error sending streak reminder to user {user.tg_id}: {e}")

    except Exception as e:
        logger.error(f"Error in check_streak_reminder: {e}")


async def weekly_stats(bot: Bot):
    """Еженедельная статистика (по воскресеньям)"""
    logger.info("Sending weekly stats...")

    try:
        all_users = await ReminderDAO.get_all_active_users()

        for user in all_users:
            try:
                stats = await GamificationDAO.get_user_stats(user.id)
                weekly_stats = await GamificationDAO.get_weekly_stats(user.id)

                level_emoji = get_level_emoji(stats.get('level', 1))

                message_text = (
                    f"📊 <b>Твоя неделя в цифрах</b>\n\n"
                    f"{level_emoji} Уровень: {stats.get('level', 1)}\n"
                    f"💫 XP за неделю: +{weekly_stats.get('xp_earned', 0)}\n\n"
                    f"<b>Задачи:</b>\n"
                    f"├ ✅ Выполнено: {weekly_stats.get('completed', 0)}\n"
                    f"├ 📝 Создано: {weekly_stats.get('created', 0)}\n"
                    f"└ 🔥 Лучший стрик: {stats.get('max_streak', 0)} дн.\n\n"
                )

                # Добавляем мотивацию
                completed = weekly_stats.get('completed', 0)
                if completed >= 20:
                    message_text += "🏆 <b>Невероятная продуктивность! Ты звезда!</b>"
                elif completed >= 10:
                    message_text += "🌟 <b>Отличная неделя! Так держать!</b>"
                elif completed >= 5:
                    message_text += "👍 <b>Хорошая работа! Можешь лучше!</b>"
                elif completed > 0:
                    message_text += "💪 <b>Неплохо! На следующей неделе сделаем больше!</b>"
                else:
                    message_text += "🌱 <b>Новая неделя — новые возможности!</b>"

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="👤 Профиль", callback_data="back_to_profile")]
                ])

                await bot.send_message(
                    chat_id=user.tg_id,
                    text=message_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )

                logger.info(f"Sent weekly stats to user {user.tg_id}")

            except Exception as e:
                logger.error(f"Error sending weekly stats to user {user.tg_id}: {e}")

    except Exception as e:
        logger.error(f"Error in weekly_stats: {e}")