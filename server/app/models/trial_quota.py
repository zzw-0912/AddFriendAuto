from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, UniqueConstraint

from app.core.database import Base


class TrialQuota(Base):
    __tablename__ = "trial_quotas"
    __table_args__ = (UniqueConstraint("user_id", name="uq_trial_quotas_user_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    device_id = Column(Integer, nullable=False)
    total_count = Column(Integer, default=20)
    used_count = Column(Integer, default=0)
    remaining_count = Column(Integer, default=20)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
