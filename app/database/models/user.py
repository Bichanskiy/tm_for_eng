from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.database.base import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    tg_id = Column(Integer)
    username = Column(String, nullable=True)

    tasks = relationship(
        "Task",
        back_populates="user",
    )
