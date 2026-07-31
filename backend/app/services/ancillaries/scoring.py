"""
Composite Opportunity Scorer for the Ancillary Revenue Engine.

Formula
───────
score = (
    propensity × 30
    + margin_norm × 25
    + demand_relevance × 20
    + segment_affinity × 15
    + event_relevance × 7
    + capacity_factor × 3
)  → float in [0, 100]

Component descriptions
──────────────────────
propensity_score (0–30):
    propensity × 30 (linear)

margin_score (0–25):
    margin_pct normalised to [0, 1] over a 0%–80% range, × 25

demand_relevance_score (0–20):
    demand_index normalised to [0, 1] over 0–100, × 20

segment_affinity_score (0–15):
    Based on whether the persona is in target_segments.
    Perfect match = 15, partial = 8, no match = 3.

event_relevance_score (0–7):
    If any applicable_event_type is active: 7. Otherwise 0.

capacity_score (0–3):
    (1 - current_utilization) × 3  (available capacity is good for promotion)

Returns the score and a fully populated AncillaryScoreComponents breakdown.
"""
from __future__ import annotations

from app.schemas.ancillaries import (
    AncillaryContext,
    AncillaryProduct,
    AncillaryScoreComponents,
    GuestPersona,
)

_MARGIN_NORM_MAX: float = 80.0  # Margin above this is treated as 100%


def score_opportunity(
    product: AncillaryProduct,
    context: AncillaryContext,
    propensity: float,
    recommended_price: float,
) -> tuple[float, AncillaryScoreComponents]:
    """
    Compute composite opportunity score for (product, context).

    Parameters
    ----------
    product:
        The ancillary product.
    context:
        Hotel + demand + guest context.
    propensity:
        Estimated conversion propensity [0, 1].
    recommended_price:
        Final recommended price after pricing adjustments.

    Returns
    -------
    (score, AncillaryScoreComponents)
    """
    # ── Propensity component (0–30) ───────────────────────────────────────────
    propensity_score = propensity * 30.0

    # ── Margin component (0–25) ───────────────────────────────────────────────
    if recommended_price > 0:
        margin_pct = (recommended_price - product.variable_cost) / recommended_price * 100.0
    else:
        margin_pct = 0.0
    margin_norm = min(1.0, max(0.0, margin_pct / _MARGIN_NORM_MAX))
    margin_score = margin_norm * 25.0

    # ── Demand relevance (0–20) ───────────────────────────────────────────────
    demand_relevance_score = (context.demand_level / 100.0) * 20.0

    # ── Segment affinity (0–15) ───────────────────────────────────────────────
    if context.persona == GuestPersona.hotel_wide:
        # Hotel-wide context: partial match (products exist for everyone)
        segment_affinity_score = 8.0
    elif context.persona in product.target_segments:
        # Perfect persona match
        segment_affinity_score = 15.0
    elif not product.target_segments:
        # Product targets all personas → moderate fit
        segment_affinity_score = 8.0
    else:
        # No match
        segment_affinity_score = 3.0

    # ── Event relevance (0–7) ─────────────────────────────────────────────────
    event_relevant = any(
        e in product.applicable_event_types for e in context.active_event_types
    )
    event_relevance_score = 7.0 if event_relevant else 0.0

    # ── Capacity factor (0–3) ─────────────────────────────────────────────────
    capacity_score = (1.0 - product.current_utilization) * 3.0

    # ── Total ─────────────────────────────────────────────────────────────────
    total = (
        propensity_score
        + margin_score
        + demand_relevance_score
        + segment_affinity_score
        + event_relevance_score
        + capacity_score
    )
    total = max(0.0, min(100.0, total))

    components = AncillaryScoreComponents(
        propensity_score=round(propensity_score, 2),
        margin_score=round(margin_score, 2),
        demand_relevance_score=round(demand_relevance_score, 2),
        segment_affinity_score=round(segment_affinity_score, 2),
        event_relevance_score=round(event_relevance_score, 2),
        capacity_score=round(capacity_score, 2),
        total=round(total, 2),
    )

    return round(total, 2), components
