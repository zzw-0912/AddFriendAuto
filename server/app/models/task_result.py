from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.core.database import Base


class TaskResult(Base):
    __tablename__ = "task_results"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, nullable=False, index=True)
    contact_id = Column(Integer, nullable=True)
    result = Column(String(20), nullable=False)
    trial_charged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
