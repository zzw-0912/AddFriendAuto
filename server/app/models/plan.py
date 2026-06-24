from sqlalchemy import Boolean, Column, Integer, String

from app.core.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    duration_days = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)
    enabled = Column(Boolean, default=True)
