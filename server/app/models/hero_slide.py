from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from app.core.database import Base


class HeroSlide(Base):
    __tablename__ = "hero_slides"
    __table_args__ = (
        UniqueConstraint("slot_index", name="uq_hero_slides_slot_index"),
    )

    id = Column(Integer, primary_key=True, index=True)
    slot_index = Column(Integer, nullable=False, index=True)
    image_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
