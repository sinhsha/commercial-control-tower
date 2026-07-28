from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import String, Date, Float, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DailyMetrics(Base):
    """
    One row per hotel per day – the core fact table.

    Extension points
    ----------------
    forecasted_occupancy  : float | None  → add when forecasting engine is ready
    recommended_rate      : float | None  → add when optimisation engine is ready
    ai_insight            : str   | None  → add when explanation engine is ready
    """

    __tablename__ = "daily_metrics"
    __table_args__ = (
        Index("ix_daily_metrics_hotel_date", "hotel_id", "date", unique=True),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    hotel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # Core commercial KPIs
    occupied_rooms: Mapped[int] = mapped_column(Integer, nullable=False)
    total_rooms: Mapped[int] = mapped_column(Integer, nullable=False)
    adr: Mapped[float] = mapped_column(Float, nullable=False)  # Average Daily Rate
    revenue: Mapped[float] = mapped_column(Float, nullable=False)

    # Demand signal (0–100 index, sourced from external feed in production)
    demand_index: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)

    # Competitive set average rate (placeholder for rate-shop integration)
    compset_adr: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    # Relationships
    hotel: Mapped["Hotel"] = relationship("Hotel", back_populates="daily_metrics")

    # ── Computed properties (no DB columns needed) ─────────────────────────

    @property
    def occupancy_pct(self) -> float:
        if self.total_rooms == 0:
            return 0.0
        return round(self.occupied_rooms / self.total_rooms * 100, 2)

    @property
    def revpar(self) -> float:
        return round(self.adr * self.occupancy_pct / 100, 2)

    @property
    def available_rooms(self) -> int:
        return self.total_rooms - self.occupied_rooms

    def __repr__(self) -> str:
        return f"<DailyMetrics hotel={self.hotel_id} date={self.date} occ={self.occupancy_pct}%>"
