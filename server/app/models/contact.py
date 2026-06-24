from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    wechat_nickname = Column(String(255), nullable=True)
    wechat_id = Column(String(255), nullable=True)
    tag = Column(String(100), nullable=True)
    status = Column(String(20), default="active")
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
