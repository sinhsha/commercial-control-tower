"""
Mock market-signal implementation.

Returns plausible but synthetic signals.  The values are seeded from the
hotel_id string so different hotels get slightly different compset profiles,
making the demo more realistic.

To replace with a real feed:
    1. Create a new class implementing MarketSignalService.
    2. Change get_market_signal_service() in app/core/dependencies.py.
    3. No rule logic changes required.
"""
from __future__ import annotations

import hashlib

from app.schemas.recommendations import MarketSignals
from app.services.market_signals.base import MarketSignalService


def _hotel_seed(hotel_id: str) -> int:
    """Deterministic integer derived from hotel_id for stable mock values."""
    digest = hashlib.md5(hotel_id.encode(), usedforsecurity=False).hexdigest()
    return int(digest[:8], 16)


class MockMarketSignalService(MarketSignalService):
    """
    Deterministic mock market signals.

    Values vary per hotel_id so each property in the demo shows different
    compset positioning.  All signals stay within realistic hospitality ranges.
    """

    async def get_signals(self, hotel_id: str) -> MarketSignals:
        seed = _hotel_seed(hotel_id)

        # Derive stable offsets from seed (deterministic, not truly random)
        comp_adr_offset = (seed % 40) - 20          # –20 to +20 USD vs ~$280 base
        comp_occ_offset = (seed % 16) - 8            # –8 to +8 pct vs ~70% base
        pace_offset = ((seed >> 4) % 30) - 10        # maps to 0.90–1.20 range
        cancel_offset = (seed % 10)                  # 0–9 added to base 5%
        premium_offset = (seed % 20)                 # 0–19 added to base 10

        return MarketSignals(
            competitor_adr=round(280.0 + comp_adr_offset, 2),
            competitor_occupancy=round(70.0 + comp_occ_offset, 1),
            booking_pace_index=round(1.0 + pace_offset / 100.0, 2),
            cancellation_rate=round(5.0 + cancel_offset, 1),
            premium_rooms_available=10 + premium_offset,
            expected_arrivals=round(80 + (seed % 60)),
        )
