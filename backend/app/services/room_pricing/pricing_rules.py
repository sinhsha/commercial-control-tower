"""
Pure pricing-rule functions for the Dynamic Room Pricing engine.

All functions are stateless and have no I/O, making them easy to unit-test.
"""
from __future__ import annotations

from app.schemas.room_pricing import RoomTypePricingRecommendation


# ── Demand multiplier ─────────────────────────────────────────────────────────

def demand_multiplier(forecast_occ: float) -> float:
    """
    Tiered demand multiplier based on forecast occupancy %.

    Thresholds:
        <50%  → 0.90
        50–65% → 0.95
        65–75% → 1.00
        75–85% → 1.08
        85–92% → 1.15
        >92%  → 1.25
    """
    if forecast_occ < 50.0:
        return 0.90
    if forecast_occ < 65.0:
        return 0.95
    if forecast_occ < 75.0:
        return 1.00
    if forecast_occ < 85.0:
        return 1.08
    if forecast_occ < 92.0:
        return 1.15
    return 1.25


# ── Scarcity multiplier ───────────────────────────────────────────────────────

def scarcity_multiplier(available: int, total: int) -> float:
    """
    Tiered scarcity multiplier based on available/total ratio.

    Thresholds:
        >60%  → 0.95
        40–60% → 1.00
        20–40% → 1.08
        10–20% → 1.15
        5–10%  → 1.22
        <5%   → 1.30
    """
    if total <= 0:
        return 1.00
    ratio = available / total
    if ratio > 0.60:
        return 0.95
    if ratio > 0.40:
        return 1.00
    if ratio > 0.20:
        return 1.08
    if ratio > 0.10:
        return 1.15
    if ratio > 0.05:
        return 1.22
    return 1.30


# ── Competitor multiplier ─────────────────────────────────────────────────────

def competitor_multiplier(hotel_adr: float, competitor_adr: float) -> float:
    """
    Competitor rate positioning multiplier.

    If hotel is priced below competitor by >15%  → 1.08
    If hotel is priced below competitor by >8%   → 1.05
    If hotel is within ±5% of competitor         → 1.00
    If hotel is above competitor by 5–10%        → 0.97
    If hotel is above competitor by >10%         → 0.94
    """
    if competitor_adr <= 0:
        return 1.00
    diff_pct = (competitor_adr - hotel_adr) / competitor_adr * 100  # positive = hotel cheaper
    if diff_pct > 15.0:
        return 1.08
    if diff_pct > 8.0:
        return 1.05
    if diff_pct > -5.0:
        return 1.00
    if diff_pct > -10.0:
        return 0.97
    return 0.94


# ── Core price computation ────────────────────────────────────────────────────

def compute_recommended_price(
    base_rate: float,
    premium_factor: float,
    demand_mult: float,
    scarcity_mult: float,
    competitor_mult: float,
    minimum_price: float,
    maximum_price: float,
    max_daily_increase_pct: float = 0.25,
    max_daily_decrease_pct: float = 0.15,
    current_price: float = 0.0,
) -> tuple[float, list[str]]:
    """
    Compute recommended price with guardrails.

    Returns (recommended_price, guardrails_applied).
    """
    guardrails: list[str] = []

    raw = base_rate * premium_factor * demand_mult * scarcity_mult * competitor_mult
    raw = round(raw, 2)

    # Daily change guardrails (only when current_price is provided)
    if current_price > 0:
        max_increase = current_price * (1 + max_daily_increase_pct)
        max_decrease = current_price * (1 - max_daily_decrease_pct)

        if raw > max_increase:
            raw = round(max_increase, 2)
            guardrails.append(f"max_daily_increase_{int(max_daily_increase_pct * 100)}pct")

        if raw < max_decrease:
            raw = round(max_decrease, 2)
            guardrails.append(f"max_daily_decrease_{int(max_daily_decrease_pct * 100)}pct")

    # Absolute floor / ceiling
    if raw < minimum_price:
        raw = round(minimum_price, 2)
        guardrails.append("minimum_price_floor")

    if raw > maximum_price:
        raw = round(maximum_price, 2)
        guardrails.append("maximum_price_ceiling")

    return raw, guardrails


# ── Hierarchy enforcement ─────────────────────────────────────────────────────

def enforce_room_hierarchy(
    recommendations: list[RoomTypePricingRecommendation],
) -> list[RoomTypePricingRecommendation]:
    """
    Ensure room_rank N+1 always has a recommended_price strictly above room_rank N.
    If a violation is found, bump the higher-rank room's price up by $1 above the lower.
    """
    sorted_recs = sorted(recommendations, key=lambda r: r.room_rank)
    for i in range(1, len(sorted_recs)):
        lower = sorted_recs[i - 1]
        upper = sorted_recs[i]
        if upper.recommended_price <= lower.recommended_price:
            new_price = round(lower.recommended_price + 1.0, 2)
            # Clamp to maximum_price
            new_price = min(new_price, upper.maximum_price)
            price_change_pct = (
                (new_price - upper.current_price) / upper.current_price * 100
                if upper.current_price > 0
                else 0.0
            )
            sorted_recs[i] = upper.model_copy(
                update={
                    "recommended_price": new_price,
                    "price_change_pct": round(price_change_pct, 2),
                    "guardrails_applied": upper.guardrails_applied + ["hierarchy_enforcement"],
                }
            )
    return sorted_recs


# ── LOS recommendation ────────────────────────────────────────────────────────

def los_recommendation(forecast_occ: float, days_out: int) -> str | None:
    """
    Return a length-of-stay restriction recommendation.

    >95% occ + days_out ≤ 3 → "min_3"
    >92% occ + days_out ≤ 7 → "min_2"
    else                     → None
    """
    if forecast_occ > 95.0 and days_out <= 3:
        return "min_3"
    if forecast_occ > 92.0 and days_out <= 7:
        return "min_2"
    return None


# ── Protection status ─────────────────────────────────────────────────────────

def protection_status(available: int, total: int, forecast_occ: float) -> str:
    """
    Determine room protection status.

    ratio < 0.10 or forecast > 92% → "protected"
    ratio < 0.20 or forecast > 85% → "hold"
    otherwise                       → "open"
    """
    ratio = (available / total) if total > 0 else 1.0
    if ratio < 0.10 or forecast_occ > 92.0:
        return "protected"
    if ratio < 0.20 or forecast_occ > 85.0:
        return "hold"
    return "open"
