"""
Ancillary Catalog Service.

AncillaryCatalogService is the abstract base.
SeededAncillaryCatalogService provides the 20-product seed catalog used by the engine.

To replace with a DB-backed catalog:
    Implement AncillaryCatalogService and change get_ancillary_catalog_service()
    in app/core/dependencies.py.  No other changes required.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.ancillaries import (
    AncillaryCategory,
    AncillaryProduct,
    GuestPersona,
    RevenueImpactTier,
)

# All valid personas short-list for "hotel wide" segment targeting
_ALL_PERSONAS: list[GuestPersona] = list(GuestPersona)


# ── Abstract base ─────────────────────────────────────────────────────────────


class AncillaryCatalogService(ABC):
    """Pluggable catalog loader.  Swap for a DB-backed implementation."""

    @abstractmethod
    def get_all_products(self) -> list[AncillaryProduct]:
        """Return full product catalog (active + inactive)."""
        ...

    def get_active_products(self) -> list[AncillaryProduct]:
        """Return only active products."""
        return [p for p in self.get_all_products() if p.is_active]


# ── Seeded catalog ────────────────────────────────────────────────────────────


class SeededAncillaryCatalogService(AncillaryCatalogService):
    """
    20-product seed catalog with realistic hospitality values.

    Products are constructed once at class level and shared across requests
    (they are immutable Pydantic models).
    """

    _PRODUCTS: list[AncillaryProduct] = [
        # 1. PARKING
        AncillaryProduct(
            code="PARKING",
            name="Self-Parking",
            description="Overnight self-parking in on-site garage or lot.",
            category=AncillaryCategory.parking_transportation,
            base_price=42.0,
            variable_cost=8.0,
            daily_capacity=150,
            current_utilization=0.82,
            revenue_impact_tier=RevenueImpactTier.high,
            requires_vehicle_flag=True,
            target_segments=[],  # hotel-wide (all who have vehicles)
            applicable_event_types=["convention", "sports", "concert", "local_festival"],
            base_propensity=0.55,
        ),
        # 2. VALET
        AncillaryProduct(
            code="VALET",
            name="Valet Parking",
            description="Full-service valet parking with priority retrieval.",
            category=AncillaryCategory.parking_transportation,
            base_price=28.0,
            variable_cost=12.0,
            daily_capacity=40,
            current_utilization=0.60,
            revenue_impact_tier=RevenueImpactTier.medium,
            requires_vehicle_flag=True,
            target_segments=[
                GuestPersona.business_traveler,
                GuestPersona.leisure_couple,
                GuestPersona.resort_guest,
            ],
            applicable_event_types=["convention", "sports", "concert", "local_festival"],
            base_propensity=0.25,
        ),
        # 3. EV_CHARGING
        AncillaryProduct(
            code="EV_CHARGING",
            name="EV Charging Station",
            description="Level 2 and DC fast charging for electric vehicles.",
            category=AncillaryCategory.parking_transportation,
            base_price=18.0,
            variable_cost=6.0,
            daily_capacity=10,
            current_utilization=0.70,
            revenue_impact_tier=RevenueImpactTier.medium,
            requires_ev_flag=True,
            target_segments=[GuestPersona.ev_traveler],
            applicable_event_types=[],
            base_propensity=0.80,
        ),
        # 4. CAR_RENTAL
        AncillaryProduct(
            code="CAR_RENTAL",
            name="On-Site Car Rental",
            description="Complimentary shuttle to rental desk; preferred partner rates.",
            category=AncillaryCategory.parking_transportation,
            base_price=95.0,
            variable_cost=55.0,
            daily_capacity=20,
            current_utilization=0.40,
            revenue_impact_tier=RevenueImpactTier.medium,
            target_segments=[
                GuestPersona.business_traveler,
                GuestPersona.leisure_couple,
                GuestPersona.family,
            ],
            applicable_event_types=[],
            base_propensity=0.12,
        ),
        # 5. FB_DIGITAL
        AncillaryProduct(
            code="FB_DIGITAL",
            name="In-Room Digital F&B Menu",
            description="Mobile ordering: breakfast, all-day dining, in-room snacks & drinks.",
            category=AncillaryCategory.food_beverage,
            base_price=38.0,
            variable_cost=14.0,
            daily_capacity=200,
            current_utilization=0.55,
            revenue_impact_tier=RevenueImpactTier.high,
            target_segments=[],  # hotel-wide
            applicable_event_types=[],
            base_propensity=0.30,
        ),
        # 6. MEETING_SMALL
        AncillaryProduct(
            code="MEETING_SMALL",
            name="Small Meeting Room (half-day)",
            description="Boardroom for 6–10 people with AV, Wi-Fi, and refreshments.",
            category=AncillaryCategory.meetings_events,
            base_price=225.0,
            variable_cost=45.0,
            daily_capacity=8,
            current_utilization=0.50,
            revenue_impact_tier=RevenueImpactTier.high,
            target_segments=[
                GuestPersona.business_traveler,
                GuestPersona.conference_attendee,
            ],
            applicable_event_types=["convention", "sports"],
            base_propensity=0.28,
        ),
        # 7. EVENT_TECH
        AncillaryProduct(
            code="EVENT_TECH",
            name="Event Technology Package",
            description="Live streaming, hybrid meeting kit, and dedicated IT support.",
            category=AncillaryCategory.meetings_events,
            base_price=150.0,
            variable_cost=40.0,
            daily_capacity=6,
            current_utilization=0.35,
            revenue_impact_tier=RevenueImpactTier.medium,
            target_segments=[
                GuestPersona.business_traveler,
                GuestPersona.conference_attendee,
            ],
            applicable_event_types=["convention"],
            base_propensity=0.18,
        ),
        # 8. SPA_BOOKING
        AncillaryProduct(
            code="SPA_BOOKING",
            name="Spa Treatment Booking",
            description="60-min signature massage or facial at on-site spa.",
            category=AncillaryCategory.spa_wellness,
            base_price=120.0,
            variable_cost=35.0,
            daily_capacity=40,
            current_utilization=0.75,
            revenue_impact_tier=RevenueImpactTier.high,
            target_segments=[
                GuestPersona.leisure_couple,
                GuestPersona.resort_guest,
                GuestPersona.family,
            ],
            applicable_event_types=[],
            base_propensity=0.22,
        ),
        # 9. POOL_DAY_PASS
        AncillaryProduct(
            code="POOL_DAY_PASS",
            name="Pool & Cabana Day Pass",
            description="Full day access to pool deck, towels, and lounge chairs.",
            category=AncillaryCategory.spa_wellness,
            base_price=45.0,
            variable_cost=10.0,
            daily_capacity=50,
            current_utilization=0.65,
            revenue_impact_tier=RevenueImpactTier.medium,
            target_segments=[
                GuestPersona.leisure_couple,
                GuestPersona.resort_guest,
                GuestPersona.family,
            ],
            applicable_event_types=[],
            base_propensity=0.25,
        ),
        # 10. AMENITY
        AncillaryProduct(
            code="AMENITY",
            name="Welcome Amenity Package",
            description="Curated in-room package: local snacks, wine, personalised note.",
            category=AncillaryCategory.guest_commerce,
            base_price=35.0,
            variable_cost=15.0,
            daily_capacity=100,
            current_utilization=0.45,
            revenue_impact_tier=RevenueImpactTier.medium,
            target_segments=[
                GuestPersona.leisure_couple,
                GuestPersona.resort_guest,
            ],
            applicable_event_types=[],
            base_propensity=0.18,
        ),
        # 11. TOURS
        AncillaryProduct(
            code="TOURS",
            name="Guided City Tour",
            description="3-hour guided walking or bus tour of top local attractions.",
            category=AncillaryCategory.experiences,
            base_price=85.0,
            variable_cost=30.0,
            daily_capacity=30,
            current_utilization=0.40,
            revenue_impact_tier=RevenueImpactTier.medium,
            target_segments=[
                GuestPersona.leisure_couple,
                GuestPersona.family,
                GuestPersona.resort_guest,
            ],
            applicable_event_types=["local_festival"],
            base_propensity=0.16,
        ),
        # 12. LOCAL_EXP
        AncillaryProduct(
            code="LOCAL_EXP",
            name="Local Experience Pass",
            description="Curated access to local markets, pop-ups, and cultural events.",
            category=AncillaryCategory.experiences,
            base_price=65.0,
            variable_cost=20.0,
            daily_capacity=40,
            current_utilization=0.35,
            revenue_impact_tier=RevenueImpactTier.medium,
            target_segments=[
                GuestPersona.leisure_couple,
                GuestPersona.family,
            ],
            applicable_event_types=["local_festival", "concert"],
            base_propensity=0.14,
        ),
        # 13. RESORT_EXP
        AncillaryProduct(
            code="RESORT_EXP",
            name="Premium Resort Experience",
            description="Private beach access, sunset cruise, or helicopter tour package.",
            category=AncillaryCategory.experiences,
            base_price=110.0,
            variable_cost=40.0,
            daily_capacity=20,
            current_utilization=0.30,
            revenue_impact_tier=RevenueImpactTier.medium,
            target_segments=[
                GuestPersona.resort_guest,
                GuestPersona.leisure_couple,
            ],
            applicable_event_types=[],
            base_propensity=0.15,
        ),
        # 14. GROUP_EXP
        AncillaryProduct(
            code="GROUP_EXP",
            name="Group Activity Package",
            description="Team-building activities, group cooking class, or trivia night.",
            category=AncillaryCategory.experiences,
            base_price=55.0,
            variable_cost=18.0,
            daily_capacity=60,
            current_utilization=0.25,
            revenue_impact_tier=RevenueImpactTier.low,
            target_segments=[
                GuestPersona.conference_attendee,
                GuestPersona.family,
            ],
            applicable_event_types=["convention"],
            base_propensity=0.10,
        ),
        # 15. FITNESS
        AncillaryProduct(
            code="FITNESS",
            name="Fitness Class Booking",
            description="Daily group classes: yoga, HIIT, cycling. Premium instructor.",
            category=AncillaryCategory.spa_wellness,
            base_price=25.0,
            variable_cost=5.0,
            daily_capacity=80,
            current_utilization=0.50,
            revenue_impact_tier=RevenueImpactTier.low,
            target_segments=[
                GuestPersona.business_traveler,
                GuestPersona.resort_guest,
            ],
            applicable_event_types=[],
            base_propensity=0.15,
        ),
        # 16. DAY_USE_ROOM
        AncillaryProduct(
            code="DAY_USE_ROOM",
            name="Day-Use Room (check-in 9am, check-out 5pm)",
            description="Private room for day use: ideal for business travellers, late flights.",
            category=AncillaryCategory.room_inventory,
            base_price=99.0,
            variable_cost=25.0,
            daily_capacity=15,
            current_utilization=0.30,
            revenue_impact_tier=RevenueImpactTier.high,
            target_segments=[
                GuestPersona.business_traveler,
                GuestPersona.conference_attendee,
            ],
            applicable_event_types=["convention", "sports"],
            base_propensity=0.20,
        ),
        # 17. WORKSPACE
        AncillaryProduct(
            code="WORKSPACE",
            name="Private Workspace (full day)",
            description="Dedicated private office with 4K monitor, ergonomic chair, and line.",
            category=AncillaryCategory.workspace,
            base_price=55.0,
            variable_cost=12.0,
            daily_capacity=30,
            current_utilization=0.40,
            revenue_impact_tier=RevenueImpactTier.high,
            target_segments=[
                GuestPersona.business_traveler,
                GuestPersona.conference_attendee,
            ],
            applicable_event_types=["convention"],
            base_propensity=0.25,
        ),
        # 18. COWORKING
        AncillaryProduct(
            code="COWORKING",
            name="Co-Working Hot Desk",
            description="Open co-working space with coffee, high-speed Wi-Fi, and printing.",
            category=AncillaryCategory.workspace,
            base_price=35.0,
            variable_cost=8.0,
            daily_capacity=25,
            current_utilization=0.35,
            revenue_impact_tier=RevenueImpactTier.medium,
            target_segments=[
                GuestPersona.business_traveler,
            ],
            applicable_event_types=["convention"],
            base_propensity=0.18,
        ),
        # 19. SLEEP_WELLNESS
        AncillaryProduct(
            code="SLEEP_WELLNESS",
            name="Sleep Wellness Kit",
            description="Premium pillow menu, sleep-tracking device, blackout kit.",
            category=AncillaryCategory.guest_commerce,
            base_price=42.0,
            variable_cost=18.0,
            daily_capacity=60,
            current_utilization=0.40,
            revenue_impact_tier=RevenueImpactTier.medium,
            target_segments=[
                GuestPersona.business_traveler,
                GuestPersona.resort_guest,
                GuestPersona.leisure_couple,
            ],
            applicable_event_types=[],
            base_propensity=0.14,
        ),
        # 20. PET_PROGRAM
        AncillaryProduct(
            code="PET_PROGRAM",
            name="Pet Welcome Program",
            description="Dog-walking, pet bed, bowls, and treats package.",
            category=AncillaryCategory.pet,
            base_price=45.0,
            variable_cost=15.0,
            daily_capacity=20,
            current_utilization=0.25,
            revenue_impact_tier=RevenueImpactTier.medium,
            requires_pet_flag=True,
            target_segments=[GuestPersona.pet_traveler],
            applicable_event_types=[],
            base_propensity=0.75,
        ),
    ]

    def get_all_products(self) -> list[AncillaryProduct]:
        return list(self._PRODUCTS)
