"""
Eligibility checker for the Ancillary Revenue Engine.

check_eligibility(product, context, guardrails) → (eligible: bool, reason: SuppressionReason | None)

Rules (in evaluation order)
────────────────────────────
1. Inactive product → PRODUCT_INACTIVE
2. Capacity at suppression threshold → NO_CAPACITY
3. EV charging requires ev_vehicle_flag (unless hotel_wide) → GUEST_NOT_ELIGIBLE
4. Pet program requires pet_flag (unless hotel_wide) → GUEST_NOT_ELIGIBLE
5. Parking requires vehicle_flag (unless hotel_wide) → GUEST_NOT_ELIGIBLE
6. Spa/pool suppress if utilization >= suppress_at_capacity_pct → NO_CAPACITY
7. Day-use room suppressed if forecast_occ > 88% → HOTEL_OCCUPANCY_TOO_HIGH
8. Meeting space eligible only for business/conference/group → SEGMENT_NOT_RELEVANT
9. Low-margin products below minimum_margin_pct → MARGIN_TOO_LOW
10. General capacity-above-promotion-max suppression → INVENTORY_CONSTRAINED
"""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.ancillaries import (
    AncillaryCategory,
    AncillaryContext,
    AncillaryProduct,
    GuestPersona,
    SuppressionReason,
)


@dataclass(frozen=True)
class EligibilityGuardrails:
    """Configurable thresholds for the eligibility checker."""

    suppress_at_capacity_pct: float = 0.95
    maximum_capacity_utilization_for_promotion: float = 0.90
    minimum_margin_pct: float = 25.0
    day_use_room_max_occupancy: float = 88.0


_DEFAULT_GUARDRAILS = EligibilityGuardrails()

# Personas considered "business/group" for meeting eligibility
_MEETING_ELIGIBLE_PERSONAS = frozenset(
    {
        GuestPersona.hotel_wide,
        GuestPersona.business_traveler,
        GuestPersona.conference_attendee,
    }
)

# Categories where high utilization means we can't take more bookings
_CAPACITY_SENSITIVE_CATEGORIES = frozenset(
    {
        AncillaryCategory.spa_wellness,
    }
)


def check_eligibility(
    product: AncillaryProduct,
    context: AncillaryContext,
    guardrails: EligibilityGuardrails = _DEFAULT_GUARDRAILS,
) -> tuple[bool, SuppressionReason | None]:
    """
    Evaluate whether a product should be offered in this context.

    Returns
    -------
    (True, None) if eligible
    (False, SuppressionReason) if suppressed
    """
    # 1. Product inactive
    if not product.is_active:
        return False, SuppressionReason.PRODUCT_INACTIVE

    # 2. Absolute capacity ceiling (util >= suppress_at_capacity_pct)
    if product.current_utilization >= guardrails.suppress_at_capacity_pct:
        return False, SuppressionReason.NO_CAPACITY

    # 3. EV charging: requires ev_vehicle_flag unless hotel_wide
    if product.requires_ev_flag:
        if context.persona != GuestPersona.hotel_wide and not context.ev_vehicle_flag:
            return False, SuppressionReason.GUEST_NOT_ELIGIBLE

    # 4. Pet program: requires pet_flag unless hotel_wide
    if product.requires_pet_flag:
        if context.persona != GuestPersona.hotel_wide and not context.pet_flag:
            return False, SuppressionReason.GUEST_NOT_ELIGIBLE

    # 5. Parking / vehicle products require vehicle_flag unless hotel_wide
    if product.requires_vehicle_flag:
        if context.persona != GuestPersona.hotel_wide and not context.vehicle_flag:
            return False, SuppressionReason.GUEST_NOT_ELIGIBLE

    # 6. Spa/wellness capacity threshold (stricter: suppress_at_capacity_pct)
    if product.category in _CAPACITY_SENSITIVE_CATEGORIES:
        if product.current_utilization >= guardrails.suppress_at_capacity_pct:
            return False, SuppressionReason.NO_CAPACITY

    # 7. Day-use room: suppress if hotel occupancy too high (no rooms to sell as day-use)
    if product.category == AncillaryCategory.room_inventory:
        if context.forecast_occupancy > guardrails.day_use_room_max_occupancy:
            return False, SuppressionReason.HOTEL_OCCUPANCY_TOO_HIGH

    # 8. Meeting space: strongly prefer business/conference segments
    if product.category == AncillaryCategory.meetings_events:
        if context.persona not in _MEETING_ELIGIBLE_PERSONAS:
            return False, SuppressionReason.SEGMENT_NOT_RELEVANT

    # 9. Margin check
    margin_pct = (product.base_price - product.variable_cost) / product.base_price * 100.0
    if margin_pct < guardrails.minimum_margin_pct:
        return False, SuppressionReason.MARGIN_TOO_LOW

    # 10. General capacity-above-promotion-max
    if product.current_utilization > guardrails.maximum_capacity_utilization_for_promotion:
        return False, SuppressionReason.INVENTORY_CONSTRAINED

    return True, None
