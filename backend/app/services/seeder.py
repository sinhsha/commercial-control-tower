"""
Mock data seeder.

Generates realistic-looking hotel data for the proof of concept.
Replace or augment with real PMS/CRS data feeds in production.
"""
from __future__ import annotations

import logging
import math
import random
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.hotel import Hotel
from app.models.daily_metrics import DailyMetrics
from app.models.room import Room

logger = logging.getLogger(__name__)

_SEED = 42
_HOTELS = [
    {
        "name": "Grand Meridian London",
        "brand": "Meridian Collection",
        "city": "London",
        "country": "United Kingdom",
        "star_rating": 5,
        "total_rooms": 320,
        "base_occupancy": 0.76,
        "base_adr": 285.0,
        "compset_adr": 270.0,
    },
    {
        "name": "Park Suites New York",
        "brand": "Park Suites",
        "city": "New York",
        "country": "United States",
        "star_rating": 4,
        "total_rooms": 280,
        "base_occupancy": 0.82,
        "base_adr": 340.0,
        "compset_adr": 325.0,
    },
    {
        "name": "Marina Bay Prestige",
        "brand": "Prestige Hotels",
        "city": "Singapore",
        "country": "Singapore",
        "star_rating": 5,
        "total_rooms": 450,
        "base_occupancy": 0.71,
        "base_adr": 420.0,
        "compset_adr": 400.0,
    },
    {
        "name": "Riviera Continental",
        "brand": "Continental",
        "city": "Paris",
        "country": "France",
        "star_rating": 4,
        "total_rooms": 195,
        "base_occupancy": 0.68,
        "base_adr": 195.0,
        "compset_adr": 185.0,
    },
    {
        "name": "Harbour View Sydney",
        "brand": "Harbour Collection",
        "city": "Sydney",
        "country": "Australia",
        "star_rating": 4,
        "total_rooms": 240,
        "base_occupancy": 0.73,
        "base_adr": 230.0,
        "compset_adr": 218.0,
    },
]

_ROOM_TYPES = [
    ("Standard", 0.40),
    ("Deluxe", 0.35),
    ("Junior Suite", 0.15),
    ("Suite", 0.10),
]


def _day_of_week_factor(d: date) -> float:
    """Weekend uplift."""
    return 1.12 if d.weekday() >= 4 else 1.0  # Fri/Sat/Sun


def _seasonal_factor(d: date) -> float:
    """Simple sinusoidal seasonality – peak in July/August."""
    day_of_year = d.timetuple().tm_yday
    return 1.0 + 0.18 * math.sin((day_of_year - 80) * 2 * math.pi / 365)


def _demand_index(occupancy: float, noise: float) -> float:
    base = occupancy * 100
    jitter = noise * 15
    return max(0.0, min(100.0, base + jitter))


async def _count_hotels(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(Hotel))
    return result.scalar_one()


async def seed_database(session: AsyncSession, days: int = 90) -> None:
    """Seed hotels, daily metrics, and demand events.  Idempotent."""
    from app.services.events.event_seeder import seed_events  # local import avoids circular

    existing = await _count_hotels(session)
    if existing > 0:
        logger.info("Database already seeded (%d hotels found). Skipping.", existing)
        return

    rng = random.Random(_SEED)
    today = date.today()
    start = today - timedelta(days=days - 1)

    logger.info("Seeding %d hotels with %d days of metrics each...", len(_HOTELS), days)

    for hotel_data in _HOTELS:
        # Hotel
        hotel = Hotel(
            name=hotel_data["name"],
            brand=hotel_data["brand"],
            city=hotel_data["city"],
            country=hotel_data["country"],
            star_rating=hotel_data["star_rating"],
            total_rooms=hotel_data["total_rooms"],
        )
        session.add(hotel)
        await session.flush()  # get hotel.id

        # Rooms
        total = hotel_data["total_rooms"]
        room_num = 100
        for room_type, share in _ROOM_TYPES:
            count = int(total * share)
            rack_multipliers = {
                "Standard": 1.0,
                "Deluxe": 1.3,
                "Junior Suite": 1.8,
                "Suite": 2.5,
            }
            rack = hotel_data["base_adr"] * rack_multipliers.get(room_type, 1.0)
            for i in range(count):
                floor = (room_num // 100)
                session.add(Room(
                    hotel_id=hotel.id,
                    room_number=str(room_num),
                    room_type=room_type,
                    floor=floor,
                    rack_rate=round(rack, 2),
                    is_available=rng.random() > 0.3,
                ))
                room_num += 1

        # Daily metrics
        for i in range(days):
            d = start + timedelta(days=i)
            factor = _day_of_week_factor(d) * _seasonal_factor(d)
            noise = rng.gauss(0, 1)

            raw_occ = hotel_data["base_occupancy"] * factor + noise * 0.04
            occupancy = max(0.05, min(0.99, raw_occ))
            occupied = int(occupancy * total)

            adr_noise = rng.gauss(0, 1)
            adr = hotel_data["base_adr"] * factor + adr_noise * 15
            adr = max(50.0, round(adr, 2))

            revenue = round(occupied * adr, 2)
            demand = round(_demand_index(occupancy, rng.gauss(0, 1)), 2)
            compset = round(hotel_data["compset_adr"] * factor + rng.gauss(0, 1) * 10, 2)

            session.add(DailyMetrics(
                hotel_id=hotel.id,
                date=d,
                occupied_rooms=occupied,
                total_rooms=total,
                adr=adr,
                revenue=revenue,
                demand_index=demand,
                compset_adr=compset,
            ))

        logger.info("  ✓ %s (%d rooms)", hotel_data["name"], total)

    # Collect created hotel objects for event seeding
    from sqlalchemy import select as sa_select
    from app.models.hotel import Hotel as _Hotel
    result = await session.execute(sa_select(_Hotel))
    all_hotels = list(result.scalars().all())
    await seed_events(session, all_hotels)

    await session.commit()
    logger.info("Seeding complete.")
