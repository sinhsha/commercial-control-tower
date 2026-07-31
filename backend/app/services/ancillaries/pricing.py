"""
Ancillary Pricing Service.

Applies dynamic pricing adjustments based on demand signals, event context,
and utilization data.  All changes are capped by guardrails.

Pricing rules by category
──────────────────────────
PARKING:
    Base $42
    +10% if occupancy > 85% AND utilization > 75%
    +16% if occupancy > 92% AND any event active (convention/sports/concert/festival)
    Capped at max_price_increase_pct

SPA:
    +5% if utilization < 50% (incentivise booking)
    (no increase when highly utilized – availability becomes the constraint)

DAY_USE_ROOM:
    -10% if occupancy < 55% (empty hotel means day-use is attractive stimulant)

WORKSPACE:
    +8% if business demand and event active

F&B:
    No major price changes; prefer ranking/placement over price manipulation.

All changes capped at ±max_price_increase_pct / max_price_decrease_pct.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.ancillaries import (
    AncillaryCategory,
    AncillaryContext,
    AncillaryProduct,
)


@dataclass(frozen=True)
class PricingGuardrails:
    """Guardrails for ancillary pricing adjustments."""

    max_ancillary_price_increase_pct: float = 20.0
    max_ancillary_price_decrease_pct: float = 15.0


_DEFAULT_GUARDRAILS = PricingGuardrails()

_PARKING_EVENT_TYPES = frozenset({"convention", "sports", "concert", "local_festival"})
_BUSINESS_DEMAND_PERSONAS_EVENTS = frozenset({"convention", "sports"})


def compute_recommended_price(
    product: AncillaryProduct,
    context: AncillaryContext,
    guardrails: PricingGuardrails = _DEFAULT_GUARDRAILS,
) -> tuple[float, str]:
    """
    Compute the recommended price for a product in a given context.

    Returns
    -------
    (recommended_price, price_change_reason)
    """
    base = product.base_price
    adjustment_pct = 0.0
    reason_parts: list[str] = []

    cat = product.category

    # ── Parking / Transportation ──────────────────────────────────────────────
    if cat == AncillaryCategory.parking_transportation:
        if product.code in ("PARKING", "VALET"):
            # +10% if high occupancy + high parking utilization
            if (
                context.forecast_occupancy > 85.0
                and product.current_utilization > 0.75
            ):
                adjustment_pct += 10.0
                reason_parts.append("High hotel demand & parking utilization")

            # Additional +6% (total +16%) if event active
            event_overlap = any(
                e in _PARKING_EVENT_TYPES for e in context.active_event_types
            )
            if context.forecast_occupancy > 92.0 and event_overlap:
                adjustment_pct += 6.0
                reason_parts.append("Active event driving peak demand")

    # ── Spa / Wellness ────────────────────────────────────────────────────────
    elif cat == AncillaryCategory.spa_wellness:
        # +5% if underutilized (drive revenue without capacity pressure)
        if product.current_utilization < 0.50:
            adjustment_pct += 5.0
            reason_parts.append("Spa utilization below 50% – incentive pricing")

    # ── Room Inventory (Day-Use) ──────────────────────────────────────────────
    elif cat == AncillaryCategory.room_inventory:
        if context.forecast_occupancy < 55.0:
            adjustment_pct -= 10.0
            reason_parts.append("Low hotel occupancy – day-use stimulation pricing")

    # ── Workspace ────────────────────────────────────────────────────────────
    elif cat == AncillaryCategory.workspace:
        has_business_event = any(
            e in _BUSINESS_DEMAND_PERSONAS_EVENTS for e in context.active_event_types
        )
        if context.has_active_event and has_business_event:
            adjustment_pct += 8.0
            reason_parts.append("Business event driving workspace demand")

    # ── Apply guardrails ──────────────────────────────────────────────────────
    max_inc = guardrails.max_ancillary_price_increase_pct
    max_dec = guardrails.max_ancillary_price_decrease_pct

    if adjustment_pct > max_inc:
        adjustment_pct = max_inc
        reason_parts.append(f"Capped at +{max_inc:.0f}% guardrail")
    elif adjustment_pct < -max_dec:
        adjustment_pct = -max_dec
        reason_parts.append(f"Floored at -{max_dec:.0f}% guardrail")

    recommended = round(base * (1.0 + adjustment_pct / 100.0), 2)
    reason = "; ".join(reason_parts) if reason_parts else "Base price — no adjustment signals"

    return recommended, reason
