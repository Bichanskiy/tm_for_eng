from sqlalchemy import Column, Integer, String, Boolean, Time, Date, BigInteger
from sqlalchemy.orm import relationship
from datetime import time, date

from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True)
    username = Column(String, nullable=True)

    # Настройки напоминаний
    reminders_enabled = Column(Boolean, default=True)
    reminder_time = Column(Time, default=time(9, 0))
    remind_before_hours = Column(Integer, default=24)

    # Геймификация
    xp = Column(Integer, default=0)  # Очки опыта
    level = Column(Integer, default=1)  # Уровень
    current_streak = Column(Integer, default=0)  # Текущий стрик
    max_streak = Column(Integer, default=0)  # Максимальный стрик
    last_completed_date = Column(Date, nullable=True)  # Дата последнего выполнения

    # Статистика
    total_completed = Column(Integer, default=0)  # Всего выполнено
    total_created = Column(Integer, default=0)  # Всего создано
    tasks_completed_today = Column(Integer, default=0)  # Выполнено сегодня
    last_activity_date = Column(Date, nullable=True)  # Дата последней активности

    tasks = relationship("Task", back_populates="user")
    achievements = relationship("UserAchievement", back_populates="user")