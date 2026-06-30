from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from app.core.database import Base


class TaskTarget(Base):
    __tablename__ = "task_targets"
    __table_args__ = (
        Index("ix_task_targets_user_type_status", "user_id", "target_type", "status"),
        Index("ix_task_targets_claimed_task", "claimed_task_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    target_type = Column(String(20), nullable=False)
    target_value = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    display_name = Column(String(255), nullable=True)
    status = Column(String(20), default="pending", nullable=False)
    claimed_task_id = Column(Integer, nullable=True)
    claimed_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    result_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
