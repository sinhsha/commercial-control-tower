"""
Default rule-based event-impact implementation.

Impact formula
──────────────
Raw uplift is computed as:

    capacity_ratio   = expected_attendance / hotel_total_rooms
    type_multiplier  = event-type lookup table
    distance_decay   = exp(-distance_miles / decay_half_life)
    strength_scale   = impact_strength  (pre-classified 0–1)

    raw_uplift = base_points
               * capacity_ratio
               * type_multiplier
               * distance_decay
               * strength_scale
               * proximity_discount(days_until_event)

Resulting uplift is clamped so it cannot take adjusted occupancy beyond 100%.
The caller handles the final clamp.

This implementation is intentionally stdlib-only and dependency-free.
Replace via dependency injection – no other code changes needed.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Final

from app.models.demand_event import DemandEvent
from app.schemas.events import EventInfluence
from app.services.events.base import EventImpactService

# ── Tuning parameters ─────────────────────────────────────────────────────────

# Maximum raw uplift (occupancy points) before modifiers
_BASE_UPLIFT_POINTS: Final[float] = 30.0

# How many hotel-room equivalents each 1 000 attendees represents
_ATTENDANCE_SCALE: Final[float] = 1_000.0

# Distance half-life: at this many miles the impact is halved
_DISTANCE_HALF_LIFE_MILES: Final[float] = 5.0

# Proximity discount: uplift is full within this many days, then decays
_PROXIMITY_FULL_DAYS: Final[int] = 30
_PROXIMITY_DECAY_DAYS: Final[int] = 90   # beyond this → minimal impact

# Per-type base multipliers (relative event "draw" to hotel stays)
_TYPE_MULTIPLIERS: Final[dict[str, float]] = {
    "convention": 1.00,       # strongest hotel-stay driver
    "concert": 0.65,
    "sports": 0.75,
    "local_festival": 0.55,
    "weather_disruption": -0.60,   # negative: travellers avoid / cancel
    "flight_disruption": -0.40,   # negative: stranded → forced occupancy offset
}

# Explanation templates per event type
_EXPLANATIONS: Final[dict[str, str]] = {
    "convention": "{name} convention demand adds ~{pts:+.1f} occ pts",
    "concert": "{name} concert demand adds ~{pts:+.1f} occ pts",
    "sports": "{name} sports event demand adds ~{pts:+.1f} occ pts",
    "local_festival": "{name} local festival adds ~{pts:+.1f} occ pts",
    "weather_disruption": "{name} weather disruption reduces demand by ~{pts:.1f} occ pts",
    "flight_disruption": "{name} flight disruption reduces demand by ~{pts:.1f} occ pts",
}


class DefaultEventImpactService(EventImpactService):
    """
    Rule-based event-impact engine.

    Swap for an ML-based implementation by changing the factory in
    ``app/core/dependencies.py`` – zero other changes required.
    """

    def compute_uplift(
        self,
        forecast_date: date,
        event: DemandEvent,
        hotel_total_rooms: int,
        days_until_event: int,
    ) -> EventInfluence | None:
        # Only affect dates within the event window
        if not (event.start_date <= forecast_date <= event.end_date):
            return None

        multiplier = _TYPE_MULTIPLIERS.get(event.event_type, 0.5)

        # Capacity ratio: how many attendees per available room
        capacity_ratio = min(
            event.expected_attendance / max(_ATTENDANCE_SCALE, 1.0),
            hotel_total_rooms / max(_ATTENDANCE_SCALE, 1.0),
        )

        # Distance decay: exponential with half-life
        distance_decay = math.exp(
            -math.log(2) * event.distance_miles / _DISTANCE_HALF_LIFE_MILES
        )

        # Proximity discount: uplifts further away are less certain
        if days_until_event <= _PROXIMITY_FULL_DAYS:
            proximity = 1.0
        elif days_until_event >= _PROXIMITY_DECAY_DAYS:
            proximity = 0.1
        else:
            # Linear decay from 1.0 at FULL_DAYS to 0.1 at DECAY_DAYS
            span = _PROXIMITY_DECAY_DAYS - _PROXIMITY_FULL_DAYS
            elapsed = days_until_event - _PROXIMITY_FULL_DAYS
            proximity = 1.0 - 0.9 * (elapsed / span)

        uplift = (
            _BASE_UPLIFT_POINTS
            * capacity_ratio
            * multiplier
            * distance_decay
            * event.impact_strength
            * proximity
        )

        # Round to one decimal; skip if negligible
        uplift = round(uplift, 1)
        if abs(uplift) < 0.1:
            return None

        template = _EXPLANATIONS.get(
            event.event_type,
            "{name} event adds ~{pts:+.1f} occ pts",
        )
        is_negative = event.event_type in ("weather_disruption", "flight_disruption")
        explanation = template.format(name=event.name, pts=abs(uplift) if is_negative else uplift)

        return EventInfluence(
            event_id=event.id,
            event_name=event.name,
            event_type=event.event_type,
            uplift_points=uplift,
            confidence=1.0,   # raw uplift; engine layer applies event.confidence weighting
            explanation=explanation,
        )
