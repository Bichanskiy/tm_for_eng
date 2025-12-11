from datetime import date, datetime
from typing import List, Optional, Tuple
from sqlalchemy import select, update, func
from app.database.base import async_session_maker
from app.database.models import User, UserAchievement, Task
from app.database.enums import TaskStatus
from app.constants.gamification import (
    ACHIEVEMENTS,
    get_xp_for_level,
    get_level_from_xp,
    get_task_xp,
)


class GamificationDAO:
    @classmethod
    async def add_xp(cls, user_id: int, xp_amount: int) -> Tuple[int, int, bool]:
        """
        Добавляет XP пользователю и возвращает (новый_xp, новый_уровень, повысился_ли_уровень)
        """
        async with async_session_maker() as session:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return 0, 1, False

            old_level = user.level
            new_xp = user.xp + xp_amount
            new_level = get_level_from_xp(new_xp)

            update_stmt = (
                update(User)
                .where(User.id == user_id)
                .values(xp=new_xp, level=new_level)
            )
            await session.execute(update_stmt)
            await session.commit()

            return new_xp, new_level, new_level > old_level

    @classmethod
    async def update_streak(cls, user_id: int) -> Tuple[int, bool, int]:
        """
        Обновляет стрик пользователя.
        Возвращает (новый_стрик, потерян_ли_стрик, старый_стрик)
        """
        async with async_session_maker() as session:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return 0, False, 0

            today = date.today()
            old_streak = user.current_streak
            streak_lost = False

            if user.last_completed_date is None:
                # Первое выполнение
                new_streak = 1
            elif user.last_completed_date == today:
                # Уже выполняли сегодня
                new_streak = user.current_streak
            elif (today - user.last_completed_date).days == 1:
                # Продолжаем стрик
                new_streak = user.current_streak + 1
            elif (today - user.last_completed_date).days > 1:
                # Стрик потерян
                new_streak = 1
                streak_lost = old_streak > 1
            else:
                new_streak = user.current_streak

            # Обновляем максимальный стрик
            new_max_streak = max(user.max_streak, new_streak)

            update_stmt = (
                update(User)
                .where(User.id == user_id)
                .values(
                    current_streak=new_streak,
                    max_streak=new_max_streak,
                    last_completed_date=today
                )
            )
            await session.execute(update_stmt)
            await session.commit()

            return new_streak, streak_lost, old_streak

    @classmethod
    async def increment_completed(cls, user_id: int) -> int:
        """Увеличивает счётчик выполненных задач и возвращает новое значение"""
        async with async_session_maker() as session:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return 0

            today = date.today()

            # Сбрасываем счётчик задач за сегодня, если это новый день
            tasks_today = user.tasks_completed_today
            if user.last_activity_date != today:
                tasks_today = 0

            new_total = user.total_completed + 1
            new_today = tasks_today + 1

            update_stmt = (
                update(User)
                .where(User.id == user_id)
                .values(
                    total_completed=new_total,
                    tasks_completed_today=new_today,
                    last_activity_date=today
                )
            )
            await session.execute(update_stmt)
            await session.commit()

            return new_total

    @classmethod
    async def increment_created(cls, user_id: int) -> int:
        """Увеличивает счётчик созданных задач"""
        async with async_session_maker() as session:
            stmt = (
                update(User)
                .where(User.id == user_id)
                .values(total_created=User.total_created + 1)
                .returning(User.total_created)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.scalar_one()

    @classmethod
    async def get_user_achievements(cls, user_id: int) -> List[str]:
        """Получает список ID достижений пользователя"""
        async with async_session_maker() as session:
            stmt = (
                select(UserAchievement.achievement_id)
                .where(UserAchievement.user_id == user_id)
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]

    @classmethod
    async def unlock_achievement(cls, user_id: int, achievement_id: str) -> bool:
        """
        Разблокирует достижение для пользователя.
        Возвращает True, если достижение было разблокировано (новое)
        """
        async with async_session_maker() as session:
            # Проверяем, есть ли уже достижение
            check_stmt = select(UserAchievement).where(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_id == achievement_id
            )
            result = await session.execute(check_stmt)
            if result.scalar_one_or_none():
                return False

            # Добавляем достижение
            achievement = UserAchievement(
                user_id=user_id,
                achievement_id=achievement_id
            )
            session.add(achievement)
            await session.commit()

            return True

    @classmethod
    async def check_and_unlock_achievements(
            cls,
            user_id: int,
            task: Optional[Task] = None
    ) -> List[str]:
        """
        Проверяет и разблокирует достижения.
        Возвращает список новых разблокированных достижений.
        """
        async with async_session_maker() as session:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return []

            unlocked = []
            current_achievements = await cls.get_user_achievements(user_id)

            # Проверяем достижения за количество задач
            task_achievements = [
                ("task_master_10", 10),
                ("task_master_50", 50),
                ("task_master_100", 100),
                ("task_master_500", 500),
            ]

            for ach_id, required in task_achievements:
                if ach_id not in current_achievements and user.total_completed >= required:
                    if await cls.unlock_achievement(user_id, ach_id):
                        unlocked.append(ach_id)

            # Проверяем достижения за стрики
            streak_achievements = [
                ("streak_3", 3),
                ("streak_7", 7),
                ("streak_30", 30),
                ("streak_100", 100),
            ]

            for ach_id, required in streak_achievements:
                if ach_id not in current_achievements and user.current_streak >= required:
                    if await cls.unlock_achievement(user_id, ach_id):
                        unlocked.append(ach_id)

            # Проверяем достижения за уровни
            level_achievements = [
                ("level_5", 5),
                ("level_10", 10),
                ("level_25", 25),
            ]

            for ach_id, required in level_achievements:
                if ach_id not in current_achievements and user.level >= required:
                    if await cls.unlock_achievement(user_id, ach_id):
                        unlocked.append(ach_id)

            # Проверяем достижение за первую задачу
            if "first_task" not in current_achievements and user.total_created >= 1:
                if await cls.unlock_achievement(user_id, "first_task"):
                    unlocked.append("first_task")

            # Проверяем достижение за скорость (5 задач за день)
            if "speed_demon" not in current_achievements and user.tasks_completed_today >= 5:
                if await cls.unlock_achievement(user_id, "speed_demon"):
                    unlocked.append("speed_demon")

            # Проверяем достижения, связанные с задачей
            if task:
                now = datetime.now()

                # Высокий приоритет
                if "high_priority" not in current_achievements and task.priority == 10:
                    if await cls.unlock_achievement(user_id, "high_priority"):
                        unlocked.append("high_priority")

                # Ранняя пташка (до 7 утра)
                if "early_bird" not in current_achievements and now.hour < 7:
                    if await cls.unlock_achievement(user_id, "early_bird"):
                        unlocked.append("early_bird")

                # Ночная сова (после полуночи до 5 утра)
                if "night_owl" not in current_achievements and 0 <= now.hour < 5:
                    if await cls.unlock_achievement(user_id, "night_owl"):
                        unlocked.append("night_owl")

                # Перфекционист (выполнено до дедлайна)
                if task.due_date and "perfectionist" not in current_achievements:
                    if now < task.due_date:
                        if await cls.unlock_achievement(user_id, "perfectionist"):
                            unlocked.append("perfectionist")

                # Без прокрастинации (в день создания)
                if "no_procrastination" not in current_achievements:
                    if task.created_at.date() == now.date():
                        if await cls.unlock_achievement(user_id, "no_procrastination"):
                            unlocked.append("no_procrastination")

            return unlocked

    @classmethod
    async def get_user_stats(cls, user_id: int) -> dict:
        """Получает полную статистику пользователя"""
        async with async_session_maker() as session:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return {}

            # Считаем задачи по статусам
            tasks_stmt = (
                select(Task.status, func.count(Task.id))
                .where(Task.user_id == user_id)
                .group_by(Task.status)
            )
            tasks_result = await session.execute(tasks_stmt)
            status_counts = dict(tasks_result.all())

            # Считаем достижения
            achievements_stmt = (
                select(func.count(UserAchievement.id))
                .where(UserAchievement.user_id == user_id)
            )
            achievements_result = await session.execute(achievements_stmt)
            achievements_count = achievements_result.scalar()

            return {
                "xp": user.xp,
                "level": user.level,
                "current_streak": user.current_streak,
                "max_streak": user.max_streak,
                "total_completed": user.total_completed,
                "total_created": user.total_created,
                "tasks_today": user.tasks_completed_today,
                "achievements_count": achievements_count,
                "total_achievements": len(ACHIEVEMENTS),
                "status_counts": status_counts,
                "xp_for_next_level": get_xp_for_level(user.level + 1),
            }

    @classmethod
    async def get_leaderboard(cls, limit: int = 10) -> List[Tuple[User, int]]:
        """Получает топ пользователей по XP"""
        async with async_session_maker() as session:
            stmt = (
                select(User)
                .order_by(User.xp.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            users = result.scalars().all()

            return [(user, idx + 1) for idx, user in enumerate(users)]