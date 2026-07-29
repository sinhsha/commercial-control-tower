"""
Abstract base class for market-signal providers.

Swap the implementation (MockMarketSignalService → a real rate-shopping feed)
by changing only get_market_signal_service() in app/core/dependencies.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.recommendations import MarketSignals


class MarketSignalService(ABC):
    """Pluggable interface for market-signal data."""

    @abstractmethod
    async def get_signals(self, hotel_id: str, hotel_adr: float = 280.0) -> MarketSignals:
        """
        Return the current market signals for *hotel_id*.

        Implementations may call a rate-shopping API, a data warehouse,
        or return mock data.  They must never raise – return fallback
        values on failure so recommendations degrade gracefully.
        """
        ...
