from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.demand_event import DemandEvent

logger = logging.getLogger(__name__)


class EventRepository:
    """Data-access layer for DemandEvent entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_for_hotel(self, hotel_id: str) -> list[DemandEvent]:
        """Return all active (non-cancelled) events for a hotel."""
        stmt = (
            select(DemandEvent)
            .where(
                and_(
                    DemandEvent.hotel_id == hotel_id,
                    DemandEvent.status != "cancelled",
                )
            )
            .order_by(DemandEvent.start_date)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, event: DemandEvent) -> DemandEvent:
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(event)
        return event

    async def get_by_id(self, event_id: str) -> DemandEvent | None:
        stmt = select(DemandEvent).where(DemandEvent.id == event_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, event: DemandEvent) -> None:
        await self._session.delete(event)
        await self._session.flush()

    async def get_overlapping(
        self, hotel_id: str, start: date, end: date
    ) -> list[DemandEvent]:
        """
        Return active events whose date range overlaps [start, end].

        Overlap condition: event.start_date <= end AND event.end_date >= start
        """
        stmt = (
            select(DemandEvent)
            .where(
                and_(
                    DemandEvent.hotel_id == hotel_id,
                    DemandEvent.status != "cancelled",
                    DemandEvent.start_date <= end,
                    DemandEvent.end_date >= start,
                )
            )
            .order_by(DemandEvent.start_date)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
