"""
Event seeder – adds realistic demand events for each seeded hotel.
Called from seed_database after hotels are created.

Events are seeded relative to today so they are always in the
forecast horizon regardless of when the demo is run.

Confidence values:
    1.0  – confirmed / already-ticketed / officially-scheduled
    0.9  – highly probable (recurring annual event, venue booked)
    0.8  – probable (early-stage confirmed)
    0.7  – likely but details not final
    0.5  – speculative / crowd-sourced signal
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.demand_event import DemandEvent

logger = logging.getLogger(__name__)


async def _count_events(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(DemandEvent))
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Template structure
#
#   hotel_name        : must match the name in the hotel seeder exactly
#   events[].days_from_today: relative start offset (negative → already started)
#   events[].duration_days  : inclusive length (1 = single day)
#   events[].confidence     : 0.0–1.0 certainty of event details
# ---------------------------------------------------------------------------

_EVENT_TEMPLATES = [
    # ── London – Grand Meridian ───────────────────────────────────────────────
    {
        "hotel_name": "Grand Meridian London",
        "events": [
            {
                "name": "Wimbledon Championships",
                "event_type": "sports",
                "days_from_today": 3,
                "duration_days": 14,
                "distance_miles": 8.5,
                "expected_attendance": 500_000,
                "impact_strength": 0.95,
                "confidence": 1.0,   # always held at AELTC, sold-out in advance
            },
            {
                "name": "Chelsea Flower Show",
                "event_type": "local_festival",
                "days_from_today": 20,
                "duration_days": 5,
                "distance_miles": 3.2,
                "expected_attendance": 160_000,
                "impact_strength": 0.80,
                "confidence": 1.0,   # RHS confirmed venue & dates
            },
            {
                "name": "Wembley Stadium Concert Series",
                "event_type": "concert",
                "days_from_today": 10,
                "duration_days": 2,
                "distance_miles": 6.5,
                "expected_attendance": 90_000,
                "impact_strength": 0.75,
                "confidence": 0.9,
            },
            {
                "name": "ExCeL London Tech Convention",
                "event_type": "convention",
                "days_from_today": 5,
                "duration_days": 3,
                "distance_miles": 7.8,
                "expected_attendance": 18_000,
                "impact_strength": 0.70,
                "confidence": 0.85,
            },
            {
                "name": "Thames Festival",
                "event_type": "local_festival",
                "days_from_today": 28,
                "duration_days": 4,
                "distance_miles": 1.8,
                "expected_attendance": 12_000,
                "impact_strength": 0.55,
                "confidence": 0.8,
            },
            {
                "name": "UK Bank Holiday Weekend",
                "event_type": "holiday",
                "days_from_today": 7,
                "duration_days": 3,
                "distance_miles": 0.0,
                "expected_attendance": 0,
                "impact_strength": 0.60,
                "confidence": 1.0,  # statutory – always happens
            },
            {
                "name": "Heathrow ATC Strike",
                "event_type": "flight_disruption",
                "days_from_today": -2,   # already started
                "duration_days": 3,
                "distance_miles": 15.0,
                "expected_attendance": 0,
                "impact_strength": 0.70,
                "confidence": 0.75,  # union action – probability not 100%
            },
        ],
    },
    # ── New York – Park Suites ────────────────────────────────────────────────
    {
        "hotel_name": "Park Suites New York",
        "events": [
            {
                "name": "New York Comic Con",
                "event_type": "convention",
                "days_from_today": 3,
                "duration_days": 4,
                "distance_miles": 1.2,
                "expected_attendance": 250_000,
                "impact_strength": 0.95,
                "confidence": 1.0,   # sold-out event, venue confirmed
            },
            {
                "name": "US Open Tennis",
                "event_type": "sports",
                "days_from_today": 12,
                "duration_days": 14,
                "distance_miles": 6.8,
                "expected_attendance": 700_000,
                "impact_strength": 0.90,
                "confidence": 1.0,   # annual, USTA confirmed
            },
            {
                "name": "New York Fashion Week",
                "event_type": "convention",
                "days_from_today": 22,
                "duration_days": 7,
                "distance_miles": 2.5,
                "expected_attendance": 150_000,
                "impact_strength": 0.85,
                "confidence": 0.95,
            },
            {
                "name": "Madison Square Garden Boxing Night",
                "event_type": "sports",
                "days_from_today": 8,
                "duration_days": 1,
                "distance_miles": 2.0,
                "expected_attendance": 20_000,
                "impact_strength": 0.80,
                "confidence": 0.90,
            },
            {
                "name": "Thanksgiving Holiday Weekend",
                "event_type": "holiday",
                "days_from_today": 15,
                "duration_days": 4,
                "distance_miles": 0.0,
                "expected_attendance": 0,
                "impact_strength": 0.70,
                "confidence": 1.0,
            },
            {
                "name": "Nor'easter Winter Storm",
                "event_type": "weather_disruption",
                "days_from_today": 18,
                "duration_days": 2,
                "distance_miles": 0.0,
                "expected_attendance": 0,
                "impact_strength": 0.65,
                "confidence": 0.55,  # weather forecasts are inherently uncertain
            },
        ],
    },
    # ── Singapore – Marina Bay Prestige ──────────────────────────────────────
    {
        "hotel_name": "Marina Bay Prestige",
        "events": [
            {
                "name": "Singapore Formula One Grand Prix",
                "event_type": "sports",
                "days_from_today": 2,
                "duration_days": 3,
                "distance_miles": 0.3,   # circuit runs past the hotel
                "expected_attendance": 260_000,
                "impact_strength": 1.00,
                "confidence": 1.0,   # confirmed F1 calendar
            },
            {
                "name": "Singapore Airshow",
                "event_type": "convention",
                "days_from_today": 7,
                "duration_days": 6,
                "distance_miles": 15.0,
                "expected_attendance": 50_000,
                "impact_strength": 0.85,
                "confidence": 0.95,
            },
            {
                "name": "Singapore National Day",
                "event_type": "holiday",
                "days_from_today": 16,
                "duration_days": 1,
                "distance_miles": 0.0,
                "expected_attendance": 0,
                "impact_strength": 0.65,
                "confidence": 1.0,  # statutory public holiday
            },
            {
                "name": "Star Cruises Inaugural Arrival",
                "event_type": "cruise_arrival",
                "days_from_today": 10,
                "duration_days": 2,
                "distance_miles": 1.8,
                "expected_attendance": 4_200,
                "impact_strength": 0.75,
                "confidence": 0.90,
            },
            {
                "name": "Changi Airport Weather Disruption",
                "event_type": "flight_disruption",
                "days_from_today": 14,
                "duration_days": 1,
                "distance_miles": 12.0,
                "expected_attendance": 0,
                "impact_strength": 0.50,
                "confidence": 0.50,
            },
        ],
    },
    # ── Paris – Riviera Continental ───────────────────────────────────────────
    {
        "hotel_name": "Riviera Continental",
        "events": [
            {
                "name": "Paris Fashion Week",
                "event_type": "convention",
                "days_from_today": 6,
                "duration_days": 7,
                "distance_miles": 2.5,
                "expected_attendance": 150_000,
                "impact_strength": 0.90,
                "confidence": 1.0,   # FHCM official calendar
            },
            {
                "name": "Roland Garros – French Open",
                "event_type": "sports",
                "days_from_today": 14,
                "duration_days": 15,
                "distance_miles": 3.0,
                "expected_attendance": 450_000,
                "impact_strength": 0.85,
                "confidence": 1.0,
            },
            {
                "name": "Bastille Day Celebrations",
                "event_type": "holiday",
                "days_from_today": 11,
                "duration_days": 2,
                "distance_miles": 1.0,
                "expected_attendance": 200_000,
                "impact_strength": 0.75,
                "confidence": 1.0,   # statutory
            },
            {
                "name": "Foire de Paris Consumer Show",
                "event_type": "convention",
                "days_from_today": 25,
                "duration_days": 11,
                "distance_miles": 4.5,
                "expected_attendance": 600_000,
                "impact_strength": 0.70,
                "confidence": 0.90,
            },
        ],
    },
    # ── Sydney – Harbour View ─────────────────────────────────────────────────
    {
        "hotel_name": "Harbour View Sydney",
        "events": [
            {
                "name": "Vivid Sydney Light Festival",
                "event_type": "local_festival",
                "days_from_today": 4,
                "duration_days": 18,
                "distance_miles": 0.8,
                "expected_attendance": 2_300_000,
                "impact_strength": 0.85,
                "confidence": 1.0,   # flagship annual city event
            },
            {
                "name": "Sydney New Year's Eve Fireworks",
                "event_type": "holiday",
                "days_from_today": 21,
                "duration_days": 2,
                "distance_miles": 0.5,
                "expected_attendance": 1_000_000,
                "impact_strength": 0.95,
                "confidence": 1.0,
            },
            {
                "name": "SCG Test Cricket – Ashes",
                "event_type": "sports",
                "days_from_today": 9,
                "duration_days": 5,
                "distance_miles": 3.5,
                "expected_attendance": 46_000,
                "impact_strength": 0.75,
                "confidence": 0.95,
            },
            {
                "name": "P&O Cruises Mass Arrival",
                "event_type": "cruise_arrival",
                "days_from_today": 6,
                "duration_days": 1,
                "distance_miles": 1.2,
                "expected_attendance": 3_800,
                "impact_strength": 0.65,
                "confidence": 0.85,
            },
            {
                "name": "Sydney Airport Fog Disruption",
                "event_type": "weather_disruption",
                "days_from_today": 13,
                "duration_days": 1,
                "distance_miles": 5.0,
                "expected_attendance": 0,
                "impact_strength": 0.45,
                "confidence": 0.50,
            },
        ],
    },
]


async def seed_events(session: AsyncSession, hotels: list) -> None:
    """
    Seed demand events for each hotel.  Idempotent – skips if events exist.

    Parameters
    ----------
    hotels:
        List of Hotel ORM objects already committed to the session.
    """
    existing = await _count_events(session)
    if existing > 0:
        logger.info("Events already seeded (%d found). Skipping.", existing)
        return

    today = date.today()
    hotel_by_name = {h.name: h for h in hotels}
    total_added = 0

    for template in _EVENT_TEMPLATES:
        hotel = hotel_by_name.get(template["hotel_name"])
        if hotel is None:
            logger.warning("Hotel %r not found – skipping its events.", template["hotel_name"])
            continue

        for ev in template["events"]:
            start = today + timedelta(days=ev["days_from_today"])
            end = start + timedelta(days=ev["duration_days"] - 1)
            session.add(DemandEvent(
                hotel_id=hotel.id,
                name=ev["name"],
                event_type=ev["event_type"],
                start_date=start,
                end_date=end,
                distance_miles=float(ev["distance_miles"]),
                expected_attendance=int(ev["expected_attendance"]),
                impact_strength=float(ev["impact_strength"]),
                confidence=float(ev["confidence"]),
                status="active",
            ))
            total_added += 1

    await session.flush()
    logger.info("Seeded %d demand events.", total_added)
