from sqlalchemy import select
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
    async def get_user_by_id(cls, user_id: int) -> User:
        async with async_session_maker() as session:
            query = (
                select(User)
                .where(User.id == user_id)
            )
            result = await session.execute(query)
            user = result.scalar_one_or_none()
            return user
