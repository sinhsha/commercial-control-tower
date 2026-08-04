from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.room_type import RoomType


class RoomTypeRepository:
    """Data-access layer for RoomType entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_hotel(self, hotel_id: str) -> list[RoomType]:
        stmt = (
            select(RoomType)
            .where(RoomType.hotel_id == hotel_id, RoomType.is_active.is_(True))
            .order_by(RoomType.room_rank)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_code(self, hotel_id: str, code: str) -> RoomType | None:
        stmt = select(RoomType).where(
            RoomType.hotel_id == hotel_id,
            RoomType.code == code,
            RoomType.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
