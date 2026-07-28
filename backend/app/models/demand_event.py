from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import String, Date, Float, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DemandEvent(Base):
    """
    An external demand signal that may affect hotel occupancy.

    Events are created by revenue managers or sourced from external feeds
    (ticketing platforms, convention bureaux, weather APIs, etc.).
    The impact engine is separate – this model is pure data.
    """

    __tablename__ = "demand_events"
    __table_args__ = (
        Index("ix_demand_events_hotel_dates", "hotel_id", "start_date", "end_date"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    hotel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # convention | concert | sports | weather_disruption | flight_disruption | local_festival | holiday | cruise_arrival

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    distance_miles: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expected_attendance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Pre-classified strength hint (0.0–1.0); the impact engine may override
    impact_strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    # Forecast confidence score (0.0–1.0): how certain we are of the event details
    # 1.0 = confirmed/ticketed, 0.5 = probable, 0.1 = speculative
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)

    # active | cancelled | completed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    hotel: Mapped["Hotel"] = relationship("Hotel", back_populates="demand_events")

    def __repr__(self) -> str:
        return (
            f"<DemandEvent {self.event_type!r} hotel={self.hotel_id} "
            f"{self.start_date}→{self.end_date}>"
        )
