from __future__ import annotations

import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hotel import Hotel

logger = logging.getLogger(__name__)


class HotelRepository:
    """Data-access layer for Hotel entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self, active_only: bool = True) -> list[Hotel]:
        stmt = select(Hotel)
        if active_only:
            stmt = stmt.where(Hotel.is_active.is_(True))
        stmt = stmt.order_by(Hotel.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, hotel_id: str) -> Hotel | None:
        stmt = select(Hotel).where(Hotel.id == hotel_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, hotel: Hotel) -> Hotel:
        self._session.add(hotel)
        await self._session.flush()
        await self._session.refresh(hotel)
        return hotel

    async def update(self, hotel: Hotel) -> Hotel:
        self._session.add(hotel)
        await self._session.flush()
        await self._session.refresh(hotel)
        return hotel

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(Hotel))
        return result.scalar_one()
