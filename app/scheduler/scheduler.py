import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scheduler(bot):
    """Настройка и запуск планировщика"""
    from app.scheduler.jobs import (
        check_upcoming_deadlines,
        check_overdue_tasks,
        send_daily_summary,
        check_streak_reminder,
        weekly_stats,
    )

    # Проверка приближающихся дедлайнов каждые 30 минут
    scheduler.add_job(
        check_upcoming_deadlines,
        trigger=IntervalTrigger(minutes=30),
        id="check_upcoming_deadlines",
        replace_existing=True,
        kwargs={"bot": bot}
    )

    # Проверка просроченных задач каждый час
    scheduler.add_job(
        check_overdue_tasks,
        trigger=IntervalTrigger(hours=1),
        id="check_overdue_tasks",
        replace_existing=True,
        kwargs={"bot": bot}
    )

    # Утренняя сводка в 9:00
    scheduler.add_job(
        send_daily_summary,
        trigger=CronTrigger(hour=9, minute=0),
        id="daily_summary",
        replace_existing=True,
        kwargs={"bot": bot}
    )

    # Напоминание о стрике в 21:00
    scheduler.add_job(
        check_streak_reminder,
        trigger=CronTrigger(hour=21, minute=0),
        id="streak_reminder",
        replace_existing=True,
        kwargs={"bot": bot}
    )

    # Еженедельная статистика по воскресеньям в 20:00
    scheduler.add_job(
        weekly_stats,
        trigger=CronTrigger(day_of_week='sun', hour=20, minute=0),
        id="weekly_stats",
        replace_existing=True,
        kwargs={"bot": bot}
    )

    scheduler.start()
    logger.info("Scheduler started with 5 jobs")