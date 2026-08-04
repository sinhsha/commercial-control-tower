"""
Abstract base for the Room Pricing & Inventory Optimization service.

Swap implementations by changing get_room_pricing_service() in dependencies.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date


class RoomPricingService(ABC):
    """ABC for dynamic room pricing and inventory optimization."""

    @abstractmethod
    async def generate_recommendations(
        self,
        hotel_id: str,
        as_of: date,
        horizon_days: int = 14,
    ):
        """Return a RoomPricingResponse with per-room-type recommendations."""
        ...

    @abstractmethod
    async def get_calendar(
        self,
        hotel_id: str,
        as_of: date,
        horizon_days: int = 14,
    ):
        """Return a RoomCalendarResponse for the given horizon."""
        ...

    @abstractmethod
    async def get_inventory(
        self,
        hotel_id: str,
        as_of: date,
    ):
        """Return an InventoryResponse with current sold/available state."""
        ...
