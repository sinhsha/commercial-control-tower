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
from app.models.room_type import RoomType

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

# Room types to seed per hotel (Marriott-style pricing)
_ROOM_TYPE_SEED = [
    {
        "code": "STANDARD_KING",
        "display_name": "Standard King",
        "capacity": 2,
        "base_rate": 189.0,
        "premium_factor": 1.0,
        "inventory_count": 60,
        "upgrade_priority": 1,
        "room_rank": 1,
    },
    {
        "code": "DOUBLE_QUEEN",
        "display_name": "Double Queen",
        "capacity": 4,
        "base_rate": 209.0,
        "premium_factor": 1.1,
        "inventory_count": 50,
        "upgrade_priority": 2,
        "room_rank": 2,
    },
    {
        "code": "DELUXE_KING",
        "display_name": "Deluxe King",
        "capacity": 2,
        "base_rate": 239.0,
        "premium_factor": 1.25,
        "inventory_count": 40,
        "upgrade_priority": 3,
        "room_rank": 3,
    },
    {
        "code": "EXEC_KING",
        "display_name": "Executive King",
        "capacity": 2,
        "base_rate": 279.0,
        "premium_factor": 1.45,
        "inventory_count": 30,
        "upgrade_priority": 4,
        "room_rank": 4,
    },
    {
        "code": "CLUB_LEVEL",
        "display_name": "Club Level",
        "capacity": 2,
        "base_rate": 319.0,
        "premium_factor": 1.6,
        "inventory_count": 20,
        "upgrade_priority": 5,
        "room_rank": 5,
    },
    {
        "code": "JR_SUITE",
        "display_name": "Junior Suite",
        "capacity": 3,
        "base_rate": 399.0,
        "premium_factor": 1.9,
        "inventory_count": 15,
        "upgrade_priority": 6,
        "room_rank": 6,
    },
    {
        "code": "EXEC_SUITE",
        "display_name": "Executive Suite",
        "capacity": 4,
        "base_rate": 499.0,
        "premium_factor": 2.3,
        "inventory_count": 8,
        "upgrade_priority": 7,
        "room_rank": 7,
    },
    {
        "code": "PRESIDENTIAL",
        "display_name": "Presidential Suite",
        "capacity": 6,
        "base_rate": 799.0,
        "premium_factor": 3.5,
        "inventory_count": 2,
        "upgrade_priority": 8,
        "room_rank": 8,
    },
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

    # Seed room types for each hotel
    for hotel in all_hotels:
        await seed_room_types(session, hotel.id)

    await session.commit()
    logger.info("Seeding complete.")


async def seed_room_types(session: AsyncSession, hotel_id: str) -> None:
    """Seed 8 Marriott-style room types for a hotel.  Idempotent."""
    from sqlalchemy import select as sa_select

    existing = await session.execute(
        sa_select(RoomType).where(RoomType.hotel_id == hotel_id)
    )
    if existing.scalars().first() is not None:
        return  # already seeded

    for rt in _ROOM_TYPE_SEED:
        base = rt["base_rate"]
        minimum_price = round(base * 0.70, 2)
        maximum_price = round(base * 2.50, 2)
        # Start with ~70% availability
        available = max(1, int(rt["inventory_count"] * 0.70))
        session.add(
            RoomType(
                hotel_id=hotel_id,
                code=rt["code"],
                display_name=rt["display_name"],
                capacity=rt["capacity"],
                base_rate=base,
                premium_factor=rt["premium_factor"],
                inventory_count=rt["inventory_count"],
                current_available=available,
                upgrade_priority=rt["upgrade_priority"],
                minimum_price=minimum_price,
                maximum_price=maximum_price,
                current_price=base,
                room_rank=rt["room_rank"],
                is_active=True,
            )
        )
    await session.flush()
    logger.info("  ✓ Seeded %d room types for hotel %s", len(_ROOM_TYPE_SEED), hotel_id)
