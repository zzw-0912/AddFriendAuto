from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint

from app.core.database import Base


class TaskResult(Base):
    __tablename__ = "task_results"
    __table_args__ = (
        UniqueConstraint("task_id", "contact_id", name="uq_task_results_task_contact"),
        UniqueConstraint("task_id", "target_id", name="uq_task_results_task_target"),
    )

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, nullable=False, index=True)
    target_id = Column(Integer, nullable=True, index=True)
    contact_id = Column(Integer, nullable=True)
    target_type = Column(String(20), nullable=True)
    result = Column(String(20), nullable=False)
    message = Column(Text, nullable=True)
    trial_charged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
