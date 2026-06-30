from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.core.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    device_id = Column(Integer, nullable=False)
    slot_id = Column(Integer, default=1, nullable=False)
    daily_limit = Column(Integer, default=20)
    create_tag = Column(Boolean, default=False)
    greeting_text = Column(Text, nullable=True)
    status = Column(String(20), default="running")
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)
