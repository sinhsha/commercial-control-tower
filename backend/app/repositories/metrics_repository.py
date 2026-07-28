from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_metrics import DailyMetrics

logger = logging.getLogger(__name__)


class MetricsRepository:
    """Data-access layer for DailyMetrics entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_hotel_and_date(
        self, hotel_id: str, target_date: date
    ) -> DailyMetrics | None:
        stmt = select(DailyMetrics).where(
            and_(
                DailyMetrics.hotel_id == hotel_id,
                DailyMetrics.date == target_date,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_range(
        self, hotel_id: str, start: date, end: date
    ) -> list[DailyMetrics]:
        stmt = (
            select(DailyMetrics)
            .where(
                and_(
                    DailyMetrics.hotel_id == hotel_id,
                    DailyMetrics.date >= start,
                    DailyMetrics.date <= end,
                )
            )
            .order_by(DailyMetrics.date)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest(self, hotel_id: str) -> DailyMetrics | None:
        stmt = (
            select(DailyMetrics)
            .where(DailyMetrics.hotel_id == hotel_id)
            .order_by(desc(DailyMetrics.date))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, metrics: DailyMetrics) -> DailyMetrics:
        existing = await self.get_by_hotel_and_date(metrics.hotel_id, metrics.date)
        if existing:
            existing.occupied_rooms = metrics.occupied_rooms
            existing.total_rooms = metrics.total_rooms
            existing.adr = metrics.adr
            existing.revenue = metrics.revenue
            existing.demand_index = metrics.demand_index
            existing.compset_adr = metrics.compset_adr
            self._session.add(existing)
            await self._session.flush()
            await self._session.refresh(existing)
            return existing

        self._session.add(metrics)
        await self._session.flush()
        await self._session.refresh(metrics)
        return metrics

    async def bulk_insert(self, records: list[DailyMetrics]) -> None:
        for record in records:
            self._session.add(record)
        await self._session.flush()
