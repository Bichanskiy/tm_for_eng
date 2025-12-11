from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Boolean,
    func
)
from sqlalchemy.orm import relationship

from app.database.base import Base
from app.database.enums import TaskStatus


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    status = Column(
        Enum(TaskStatus, name="task_status"),
        nullable=False,
        default=TaskStatus.PENDING
    )
    priority = Column(
        Integer,
        nullable=True,
        default=1
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Флаги для напоминаний
    reminder_sent = Column(Boolean, default=False)  # Отправлено ли напоминание о приближающемся сроке
    overdue_reminder_sent = Column(Boolean, default=False)  # Отправлено ли напоминание о просрочке

    user = relationship("User", back_populates="tasks")