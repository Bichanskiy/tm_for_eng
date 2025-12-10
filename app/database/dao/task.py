from datetime import datetime
from typing import List, Optional
from sqlalchemy import delete, select, update, func
from app.database.base import async_session_maker
from app.database.enums import TaskStatus
from app.database.models import Task


class TaskDAO:
    # Добавляем константу для пагинации
    TASKS_PER_PAGE = 5

    @classmethod
    async def create_and_get_task(
            cls,
            user_id: int,
            title: str,
            description: str,
            priority: int | None = 1,
            due_date: datetime | None = None,
    ) -> Task:
        async with async_session_maker() as session:
            task = Task(
                user_id=user_id,
                title=title,
                description=description,
                priority=priority,
                due_date=due_date,
            )

            session.add(task)
            await session.commit()
            await session.refresh(task)

            return task

    @classmethod
    async def get_task(
            cls,
            task_id: int,
            user_id: int,
    ) -> Optional[Task]:
        async with async_session_maker() as session:
            stmt = (
                select(Task)
                .where(
                    Task.id == task_id,
                    Task.user_id == user_id,
                )
            )

            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    @classmethod
    async def get_tasks(
            cls,
            user_id: int,
            status: TaskStatus | None = None,
            only_overdue: bool = False,
            limit: int | None = None,
            offset: int | None = None,
    ) -> List[Task]:
        async with async_session_maker() as session:
            stmt = select(Task).where(Task.user_id == user_id)

            if status:
                stmt = stmt.where(Task.status == status)

            if only_overdue:
                stmt = stmt.where(
                    Task.due_date.isnot(None),
                    Task.due_date < datetime.utcnow(),
                    Task.status != TaskStatus.COMPLETED,
                )

            stmt = stmt.order_by(Task.created_at.desc())

            if limit:
                stmt = stmt.limit(limit)
            if offset:
                stmt = stmt.offset(offset)

            result = await session.execute(stmt)
            return result.scalars().all()

    @classmethod
    async def update_and_get_task(
            cls,
            task_id: int,
            user_id: int,
            title: str | None = None,
            description: str | None = None,
            priority: int | None = None,
            due_date: datetime | None = None,
            status: TaskStatus | None = None,
    ) -> Optional[Task]:
        async with async_session_maker() as session:
            stmt = (
                update(Task)
                .where(Task.id == task_id, Task.user_id == user_id)
                .values(
                    **{
                        k: v
                        for k, v in {
                            "title": title,
                            "description": description,
                            "priority": priority,
                            "due_date": due_date,
                            "status": status,
                        }.items()
                        if v is not None
                    }
                )
                .returning(Task)
            )

            result = await session.execute(stmt)
            task = result.scalar_one_or_none()

            if task:
                await session.commit()

            return task

    @classmethod
    async def mark_status(
            cls,
            task_id: int,
            user_id: int,
            status: TaskStatus,
    ) -> Optional[Task]:
        """
        Отмечаем задачу каким-то статусом status
        """
        async with async_session_maker() as session:
            stmt = (
                update(Task)
                .where(Task.id == task_id, Task.user_id == user_id)
                .values(
                    status=status,
                    completed_at=datetime.utcnow() if status == TaskStatus.COMPLETED else None,
                )
                .returning(Task)
            )

            result = await session.execute(stmt)
            task = result.scalar_one_or_none()

            if task:
                await session.commit()
            return task

    @classmethod
    async def delete_task(
            cls,
            task_id: int,
            user_id: int,
    ) -> bool:
        """
            Удаляет задачу и возвращает True, если удалена хотя бы одна (на практике он только одну и удалит),
            если не была удалена, то возвращает False
        """
        async with async_session_maker() as session:
            stmt = (
                delete(Task)
                .where(
                    Task.id == task_id,
                    Task.user_id == user_id,
                )
            )

            result = await session.execute(stmt)
            await session.commit()

            return result.rowcount > 0

    @classmethod
    async def count_tasks(cls, user_id: int) -> int:
        """Подсчет общего количества задач пользователя"""
        async with async_session_maker() as session:
            stmt = select(func.count(Task.id)).where(Task.user_id == user_id)
            result = await session.execute(stmt)
            return result.scalar()