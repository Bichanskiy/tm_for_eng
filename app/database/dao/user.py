from datetime import time
from typing import Optional
from sqlalchemy import select, update
from app.database.base import async_session_maker
from app.database.models import User


class UserDAO:
    @classmethod
    async def get_or_create_user(cls, telegram_user) -> User:
        async with async_session_maker() as session:
            query = (
                select(User)
                .where(User.tg_id == telegram_user.id)
            )
            result = await session.execute(query)
            user = result.scalar_one_or_none()

            if user:
                return user

            user = User(
                tg_id=telegram_user.id,
                username=telegram_user.username
            )

            session.add(user)
            await session.commit()
            await session.refresh(user)

            return user

    @classmethod
    async def get_user_by_id(cls, user_id: int) -> Optional[User]:
        async with async_session_maker() as session:
            query = (
                select(User)
                .where(User.id == user_id)
            )
            result = await session.execute(query)
            user = result.scalar_one_or_none()
            return user

    @classmethod
    async def update_reminder_settings(
            cls,
            user_id: int,
            reminders_enabled: Optional[bool] = None,
            reminder_time: Optional[time] = None,
            remind_before_hours: Optional[int] = None
    ) -> Optional[User]:
        async with async_session_maker() as session:
            update_data = {}
            if reminders_enabled is not None:
                update_data['reminders_enabled'] = reminders_enabled
            if reminder_time is not None:
                update_data['reminder_time'] = reminder_time
            if remind_before_hours is not None:
                update_data['remind_before_hours'] = remind_before_hours

            if not update_data:
                return None

            stmt = (
                update(User)
                .where(User.id == user_id)
                .values(**update_data)
                .returning(User)
            )

            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if user:
                await session.commit()

            return user