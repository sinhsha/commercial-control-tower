from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models.hotel import Hotel
from app.repositories.hotel_repository import HotelRepository
from app.schemas.hotel import HotelCreate, HotelUpdate

logger = logging.getLogger(__name__)


class HotelService:
    """Business logic for hotel management."""

    def __init__(self, repo: HotelRepository) -> None:
        self._repo = repo

    async def list_hotels(self, active_only: bool = True) -> list[Hotel]:
        return await self._repo.get_all(active_only=active_only)

    async def get_hotel(self, hotel_id: str) -> Hotel | None:
        return await self._repo.get_by_id(hotel_id)

    async def create_hotel(self, data: HotelCreate) -> Hotel:
        hotel = Hotel(**data.model_dump())
        created = await self._repo.create(hotel)
        logger.info("Created hotel id=%s name=%r", created.id, created.name)
        return created

    async def update_hotel(self, hotel_id: str, data: HotelUpdate) -> Hotel | None:
        hotel = await self._repo.get_by_id(hotel_id)
        if hotel is None:
            return None
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(hotel, field, value)
        hotel.updated_at = datetime.now(timezone.utc)
        updated = await self._repo.update(hotel)
        logger.info("Updated hotel id=%s fields=%s", hotel_id, list(updates.keys()))
        return updated

    async def count_hotels(self) -> int:
        return await self._repo.count()
