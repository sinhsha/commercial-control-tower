from __future__ import annotations

import logging
from datetime import date, timedelta

from app.models.daily_metrics import DailyMetrics
from app.repositories.hotel_repository import HotelRepository
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.hotel import DashboardSummary, DemandPoint

logger = logging.getLogger(__name__)

_TREND_DAYS = 30


class MetricsService:
    """
    Business logic for commercial metrics.

    Future extension points
    -----------------------
    - Inject a ForecastingService to populate `forecasted_occupancy`
    - Inject an OptimizationService to populate `recommended_rate`
    - Inject an ExplanationService to populate `ai_insight`
    """

    def __init__(
        self,
        hotel_repo: HotelRepository,
        metrics_repo: MetricsRepository,
    ) -> None:
        self._hotel_repo = hotel_repo
        self._metrics_repo = metrics_repo

    async def get_dashboard(
        self,
        hotel_id: str,
        as_of: date | None = None,
    ) -> DashboardSummary | None:
        hotel = await self._hotel_repo.get_by_id(hotel_id)
        if hotel is None:
            return None

        target = as_of or date.today()

        # Today's snapshot
        today_metrics = await self._metrics_repo.get_by_hotel_and_date(hotel_id, target)
        if today_metrics is None:
            # Fall back to the latest available record
            today_metrics = await self._metrics_repo.get_latest(hotel_id)
        if today_metrics is None:
            return None

        # 30-day trend
        trend_start = target - timedelta(days=_TREND_DAYS - 1)
        trend_records = await self._metrics_repo.get_range(hotel_id, trend_start, target)
        trend = [
            DemandPoint(
                date=r.date,
                demand_index=r.demand_index,
                occupancy_pct=r.occupancy_pct,
                adr=r.adr,
            )
            for r in trend_records
        ]

        return DashboardSummary(
            hotel_id=hotel.id,
            hotel_name=hotel.name,
            as_of_date=target,
            occupancy_pct=today_metrics.occupancy_pct,
            adr=today_metrics.adr,
            revpar=today_metrics.revpar,
            available_rooms=today_metrics.available_rooms,
            total_rooms=today_metrics.total_rooms,
            occupied_rooms=today_metrics.occupied_rooms,
            demand_index=today_metrics.demand_index,
            compset_adr=today_metrics.compset_adr,
            demand_trend=trend,
            # Extension fields – None until AI engines are wired in
            forecasted_occupancy=None,
            recommended_rate=None,
            ai_insight=None,
        )

    async def get_metrics_range(
        self, hotel_id: str, start: date, end: date
    ) -> list[DailyMetrics]:
        return await self._metrics_repo.get_range(hotel_id, start, end)
