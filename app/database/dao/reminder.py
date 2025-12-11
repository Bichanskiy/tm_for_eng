from datetime import datetime, timedelta
from typing import List, Tuple
from sqlalchemy import select, update, and_
from app.database.base import async_session_maker
from app.database.models import Task, User
from app.database.enums import TaskStatus


class ReminderDAO:
    @classmethod
    async def get_tasks_for_reminder(cls) -> List[Tuple[Task, User]]:
        """
        Получает задачи, для которых нужно отправить напоминание о приближающемся сроке
        """
        async with async_session_maker() as session:
            now = datetime.utcnow()

            stmt = (
                select(Task, User)
                .join(User, Task.user_id == User.id)
                .where(
                    and_(
                        Task.due_date.isnot(None),
                        Task.status != TaskStatus.COMPLETED,
                        Task.status != TaskStatus.CANCELLED,
                        Task.reminder_sent == False,
                        User.reminders_enabled == True,
                        # Срок наступает в течение remind_before_hours часов
                        Task.due_date <= now + timedelta(hours=24),
                        Task.due_date > now,
                    )
                )
            )

            result = await session.execute(stmt)
            return result.all()

    @classmethod
    async def get_overdue_tasks(cls) -> List[Tuple[Task, User]]:
        """
        Получает просроченные задачи, для которых не отправлялось напоминание
        """
        async with async_session_maker() as session:
            now = datetime.utcnow()

            stmt = (
                select(Task, User)
                .join(User, Task.user_id == User.id)
                .where(
                    and_(
                        Task.due_date.isnot(None),
                        Task.due_date < now,
                        Task.status != TaskStatus.COMPLETED,
                        Task.status != TaskStatus.CANCELLED,
                        Task.overdue_reminder_sent == False,
                        User.reminders_enabled == True,
                    )
                )
            )

            result = await session.execute(stmt)
            return result.all()

    @classmethod
    async def get_daily_summary(cls) -> List[Tuple[User, List[Task]]]:
        """
        Получает пользователей с их задачами на сегодня для утренней сводки
        """
        async with async_session_maker() as session:
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)

            # Получаем пользователей с включенными напоминаниями
            users_stmt = select(User).where(User.reminders_enabled == True)
            users_result = await session.execute(users_stmt)
            users = users_result.scalars().all()

            result = []
            for user in users:
                # Задачи на сегодня
                tasks_stmt = (
                    select(Task)
                    .where(
                        and_(
                            Task.user_id == user.id,
                            Task.status != TaskStatus.COMPLETED,
                            Task.status != TaskStatus.CANCELLED,
                        )
                    )
                    .order_by(Task.priority.desc(), Task.due_date.asc())
                )
                tasks_result = await session.execute(tasks_stmt)
                tasks = tasks_result.scalars().all()

                if tasks:
                    result.append((user, tasks))

            return result

    @classmethod
    async def mark_reminder_sent(cls, task_id: int) -> None:
        """Отмечает, что напоминание отправлено"""
        async with async_session_maker() as session:
            stmt = (
                update(Task)
                .where(Task.id == task_id)
                .values(reminder_sent=True)
            )
            await session.execute(stmt)
            await session.commit()

    @classmethod
    async def mark_overdue_reminder_sent(cls, task_id: int) -> None:
        """Отмечает, что напоминание о просрочке отправлено"""
        async with async_session_maker() as session:
            stmt = (
                update(Task)
                .where(Task.id == task_id)
                .values(overdue_reminder_sent=True)
            )
            await session.execute(stmt)
            await session.commit()

    @classmethod
    async def reset_reminder_flags(cls, task_id: int) -> None:
        """Сбрасывает флаги напоминаний (при изменении due_date)"""
        async with async_session_maker() as session:
            stmt = (
                update(Task)
                .where(Task.id == task_id)
                .values(
                    reminder_sent=False,
                    overdue_reminder_sent=False
                )
            )
            await session.execute(stmt)
            await session.commit()