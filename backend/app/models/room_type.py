from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RoomType(Base):
    __tablename__ = "room_types"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    hotel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    base_rate: Mapped[float] = mapped_column(Float, nullable=False)
    premium_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    inventory_count: Mapped[int] = mapped_column(Integer, nullable=False)
    current_available: Mapped[int] = mapped_column(Integer, nullable=False)
    upgrade_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    minimum_price: Mapped[float] = mapped_column(Float, nullable=False)
    maximum_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    room_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    def __repr__(self) -> str:
        return f"<RoomType id={self.id} code={self.code!r} hotel={self.hotel_id!r}>"
