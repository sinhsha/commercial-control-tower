"""
Propensity Scoring Service for the Ancillary Revenue Engine.

Formula (deterministic, replaceable by an ML model)
────────────────────────────────────────────────────
propensity = clamp(
    base_rate
    + segment_affinity
    + event_boost
    + stay_length_factor
    + demand_level_factor
    + capacity_factor,
    min=0.05, max=0.95
)

Components
──────────
base_rate          : product.base_propensity  (0–1)
segment_affinity   : lookup table (persona × category) → ±0.10
event_boost        : +0.08 if any applicable_event_type is active
stay_length_factor : +0.02 per night beyond 1 night, max +0.06
demand_level_factor: +0.05 if demand_index >= 70;  -0.05 if < 40
capacity_factor    : -0.05 if utilization > 0.85 (guests sense unavailability)

This formula is intentionally transparent and deterministic so it can be
unit-tested and explained to revenue managers.  Replace with an ML model by
swapping PropensityScoringService in the DI container.
"""
from __future__ import annotations

from app.schemas.ancillaries import (
    AncillaryCategory,
    AncillaryContext,
    AncillaryProduct,
    GuestPersona,
)

# ── Segment affinity table (persona × category → adjustment) ──────────────────
# Positive = this persona is more likely to buy; negative = less likely.

_SEGMENT_AFFINITY: dict[tuple[GuestPersona, AncillaryCategory], float] = {
    # Parking / Transportation
    (GuestPersona.business_traveler, AncillaryCategory.parking_transportation): 0.08,
    (GuestPersona.conference_attendee, AncillaryCategory.parking_transportation): 0.06,
    (GuestPersona.family, AncillaryCategory.parking_transportation): 0.05,
    (GuestPersona.ev_traveler, AncillaryCategory.parking_transportation): 0.10,
    (GuestPersona.pet_traveler, AncillaryCategory.parking_transportation): 0.04,
    (GuestPersona.resort_guest, AncillaryCategory.parking_transportation): -0.03,
    # Food & Beverage
    (GuestPersona.business_traveler, AncillaryCategory.food_beverage): 0.06,
    (GuestPersona.conference_attendee, AncillaryCategory.food_beverage): 0.04,
    (GuestPersona.leisure_couple, AncillaryCategory.food_beverage): 0.05,
    (GuestPersona.family, AncillaryCategory.food_beverage): 0.08,
    (GuestPersona.resort_guest, AncillaryCategory.food_beverage): 0.06,
    # Meetings & Events
    (GuestPersona.business_traveler, AncillaryCategory.meetings_events): 0.10,
    (GuestPersona.conference_attendee, AncillaryCategory.meetings_events): 0.10,
    (GuestPersona.leisure_couple, AncillaryCategory.meetings_events): -0.08,
    (GuestPersona.family, AncillaryCategory.meetings_events): -0.06,
    (GuestPersona.resort_guest, AncillaryCategory.meetings_events): -0.05,
    # Spa / Wellness
    (GuestPersona.leisure_couple, AncillaryCategory.spa_wellness): 0.09,
    (GuestPersona.resort_guest, AncillaryCategory.spa_wellness): 0.10,
    (GuestPersona.family, AncillaryCategory.spa_wellness): 0.05,
    (GuestPersona.business_traveler, AncillaryCategory.spa_wellness): 0.04,
    (GuestPersona.conference_attendee, AncillaryCategory.spa_wellness): 0.02,
    # Experiences
    (GuestPersona.leisure_couple, AncillaryCategory.experiences): 0.08,
    (GuestPersona.family, AncillaryCategory.experiences): 0.08,
    (GuestPersona.resort_guest, AncillaryCategory.experiences): 0.06,
    (GuestPersona.business_traveler, AncillaryCategory.experiences): -0.05,
    (GuestPersona.conference_attendee, AncillaryCategory.experiences): -0.03,
    # Workspace
    (GuestPersona.business_traveler, AncillaryCategory.workspace): 0.10,
    (GuestPersona.conference_attendee, AncillaryCategory.workspace): 0.07,
    (GuestPersona.leisure_couple, AncillaryCategory.workspace): -0.08,
    (GuestPersona.family, AncillaryCategory.workspace): -0.06,
    (GuestPersona.resort_guest, AncillaryCategory.workspace): -0.05,
    # Guest Commerce
    (GuestPersona.leisure_couple, AncillaryCategory.guest_commerce): 0.06,
    (GuestPersona.resort_guest, AncillaryCategory.guest_commerce): 0.05,
    (GuestPersona.business_traveler, AncillaryCategory.guest_commerce): 0.03,
    # Pet
    (GuestPersona.pet_traveler, AncillaryCategory.pet): 0.10,
    (GuestPersona.hotel_wide, AncillaryCategory.pet): -0.05,
    (GuestPersona.business_traveler, AncillaryCategory.pet): -0.08,
    # Room Inventory
    (GuestPersona.business_traveler, AncillaryCategory.room_inventory): 0.08,
    (GuestPersona.conference_attendee, AncillaryCategory.room_inventory): 0.06,
    (GuestPersona.leisure_couple, AncillaryCategory.room_inventory): -0.04,
    (GuestPersona.family, AncillaryCategory.room_inventory): -0.06,
}

_PROPENSITY_MIN: float = 0.05
_PROPENSITY_MAX: float = 0.95
_EVENT_BOOST: float = 0.08
_STAY_BOOST_PER_NIGHT: float = 0.02
_STAY_BOOST_MAX: float = 0.06
_HIGH_DEMAND_BOOST: float = 0.05
_LOW_DEMAND_PENALTY: float = -0.05
_HIGH_UTILIZATION_PENALTY: float = -0.05
_HIGH_DEMAND_THRESHOLD: float = 70.0
_LOW_DEMAND_THRESHOLD: float = 40.0
_HIGH_UTILIZATION_THRESHOLD: float = 0.85


class PropensityScoringService:
    """
    Deterministic propensity scorer.

    All inputs must be provided via AncillaryContext – no hidden state.
    Replace this class with an MLPropensityScoringService and update the
    DI factory in app/core/dependencies.py to switch to an ML model.
    """

    def score(
        self,
        product: AncillaryProduct,
        context: AncillaryContext,
    ) -> float:
        """
        Compute conversion propensity for (product, context).

        Returns
        -------
        float in [0.05, 0.95]
        """
        p = product.base_propensity

        # Segment affinity
        p += _SEGMENT_AFFINITY.get((context.persona, product.category), 0.0)

        # Event boost
        if any(e in product.applicable_event_types for e in context.active_event_types):
            p += _EVENT_BOOST

        # Stay length factor (+0.02/night beyond 1 night, max +0.06)
        extra_nights = max(0.0, context.avg_stay_length - 1.0)
        p += min(_STAY_BOOST_MAX, extra_nights * _STAY_BOOST_PER_NIGHT)

        # Demand level factor
        if context.demand_level >= _HIGH_DEMAND_THRESHOLD:
            p += _HIGH_DEMAND_BOOST
        elif context.demand_level < _LOW_DEMAND_THRESHOLD:
            p += _LOW_DEMAND_PENALTY

        # Capacity factor (guests perceive limited availability as off-putting)
        if product.current_utilization > _HIGH_UTILIZATION_THRESHOLD:
            p += _HIGH_UTILIZATION_PENALTY

        # Clamp
        return max(_PROPENSITY_MIN, min(_PROPENSITY_MAX, p))
