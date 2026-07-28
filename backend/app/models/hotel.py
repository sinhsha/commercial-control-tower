from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    star_rating: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    total_rooms: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # Relationships
    rooms: Mapped[list["Room"]] = relationship(
        "Room", back_populates="hotel", cascade="all, delete-orphan"
    )
    daily_metrics: Mapped[list["DailyMetrics"]] = relationship(
        "DailyMetrics", back_populates="hotel", cascade="all, delete-orphan"
    )
    demand_events: Mapped[list["DemandEvent"]] = relationship(
        "DemandEvent", back_populates="hotel", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Hotel id={self.id} name={self.name!r}>"
