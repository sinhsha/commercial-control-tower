from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    hotel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_number: Mapped[str] = mapped_column(String(10), nullable=False)
    room_type: Mapped[str] = mapped_column(String(50), nullable=False)  # Standard/Deluxe/Suite
    floor: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rack_rate: Mapped[float] = mapped_column(Float, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    hotel: Mapped["Hotel"] = relationship("Hotel", back_populates="rooms")

    def __repr__(self) -> str:
        return f"<Room {self.room_number} ({self.room_type}) hotel={self.hotel_id}>"
