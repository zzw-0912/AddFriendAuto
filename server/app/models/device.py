from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.core.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    machine_code_hash = Column(String(255), nullable=False)
    status = Column(String(20), default="active")
    bound_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, nullable=True)
    remark = Column(String(500), nullable=True)
