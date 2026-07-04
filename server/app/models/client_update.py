from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.core.database import Base


class ClientUpdateConfig(Base):
    __tablename__ = "client_update_configs"

    id = Column(Integer, primary_key=True, index=True)
    latest_version = Column(String(50), default="0.1.0", nullable=False)
    force_update_enabled = Column(Boolean, default=False, nullable=False)
    download_url = Column(String(1000), nullable=True)
    qr_image_path = Column(String(500), nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
