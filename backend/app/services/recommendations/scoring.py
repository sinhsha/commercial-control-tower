"""
Recommendation scoring and ranking utilities.

Scoring formula
───────────────
score = (
    revenue_component     * 0.35   # expected_revenue_impact normalised to [0,1]
  + urgency_component     * 0.25   # days_until_effective (closer = more urgent)
  + confidence_component  * 0.20   # high=1.0, medium=0.6, low=0.3
  + occupancy_component   * 0.15   # adjusted occupancy normalised to [0,1]
  + event_component       * 0.05   # whether an active event is driving demand
) * 100

The result is a float in [0, 100].  Higher = more urgent to act on.

Priority thresholds (applied after scoring):
    score >= 75 → critical
    score >= 55 → high
    score >= 35 → medium
    score <  35 → low

Minimum confidence for 'critical' priority:
    Only 'high' confidence recommendations may be critical.
    'medium' confidence caps at 'high' priority.
    'low' confidence caps at 'medium' priority.

Conflict suppression (applied before scoring):
    - increase_rate and reduce_rate cannot coexist for the same period.
    - protect_premium_inventory and release_premium_inventory cannot coexist.
    - close_discounted_rates and launch_event_package cannot coexist unless
      the package has no inherent discount (ancillary add-ons are fine).

The scoring component is separately testable from the rule engine.
"""
from __future__ import annotations

import math
from datetime import date

from app.schemas.recommendations import (
    Recommendation,
    RecommendationAction,
    RecommendationConfidence,
    RecommendationPriority,
)

# Conflict pairs: if both actions appear in the list, keep the higher-scored one.
_CONFLICT_PAIRS: list[tuple[RecommendationAction, RecommendationAction]] = [
    (RecommendationAction.increase_rate, RecommendationAction.reduce_rate),
    (
        RecommendationAction.protect_premium_inventory,
        RecommendationAction.release_premium_inventory,
    ),
    (
        RecommendationAction.close_discounted_rates,
        RecommendationAction.launch_event_package,
    ),
]

# Confidence caps on priority
_CONFIDENCE_PRIORITY_CAP: dict[RecommendationConfidence, RecommendationPriority] = {
    RecommendationConfidence.high: RecommendationPriority.critical,
    RecommendationConfidence.medium: RecommendationPriority.high,
    RecommendationConfidence.low: RecommendationPriority.medium,
}

_PRIORITY_ORDER = [
    RecommendationPriority.critical,
    RecommendationPriority.high,
    RecommendationPriority.medium,
    RecommendationPriority.low,
]


def _revenue_component(expected_revenue_impact: float) -> float:
    """Normalise revenue impact to [0, 1] using a soft cap at $25,000."""
    if expected_revenue_impact <= 0:
        return 0.0
    return min(1.0, expected_revenue_impact / 25_000.0)


def _urgency_component(as_of: date, effective_start: date) -> float:
    """Closer effective dates score higher urgency.  Same-day = 1.0, 14+ days = 0.0."""
    days_away = max(0, (effective_start - as_of).days)
    return max(0.0, 1.0 - days_away / 14.0)


def _confidence_component(confidence: RecommendationConfidence) -> float:
    return {
        RecommendationConfidence.high: 1.0,
        RecommendationConfidence.medium: 0.6,
        RecommendationConfidence.low: 0.3,
    }[confidence]


def _occupancy_component(adjusted_occupancy: float) -> float:
    """Scale occupancy (0–100) to [0, 1]."""
    return max(0.0, min(1.0, adjusted_occupancy / 100.0))


def _event_component(has_active_event: bool) -> float:
    return 1.0 if has_active_event else 0.0


def compute_score(
    expected_revenue_impact: float,
    confidence: RecommendationConfidence,
    effective_start: date,
    as_of: date,
    adjusted_occupancy: float,
    has_active_event: bool,
) -> float:
    """
    Compute a composite recommendation score in [0, 100].

    Parameters
    ----------
    expected_revenue_impact:  Estimated USD uplift (label as estimate in UI).
    confidence:               Engine confidence level.
    effective_start:          First date the recommendation applies.
    as_of:                    The date recommendations are generated for.
    adjusted_occupancy:       Event-adjusted occupancy forecast (0–100).
    has_active_event:         True if a demand event is driving this recommendation.
    """
    raw = (
        _revenue_component(expected_revenue_impact) * 0.35
        + _urgency_component(as_of, effective_start) * 0.25
        + _confidence_component(confidence) * 0.20
        + _occupancy_component(adjusted_occupancy) * 0.15
        + _event_component(has_active_event) * 0.05
    )
    return round(raw * 100.0, 2)


def assign_priority(score: float, confidence: RecommendationConfidence) -> RecommendationPriority:
    """
    Map a numeric score to a priority level, capped by confidence.

    A low-confidence recommendation cannot be critical even if its score
    is very high (avoids false alarms).
    """
    if score >= 75:
        raw_priority = RecommendationPriority.critical
    elif score >= 55:
        raw_priority = RecommendationPriority.high
    elif score >= 35:
        raw_priority = RecommendationPriority.medium
    else:
        raw_priority = RecommendationPriority.low

    cap = _CONFIDENCE_PRIORITY_CAP[confidence]
    # Use the less-urgent of raw_priority and the cap
    raw_idx = _PRIORITY_ORDER.index(raw_priority)
    cap_idx = _PRIORITY_ORDER.index(cap)
    return _PRIORITY_ORDER[max(raw_idx, cap_idx)]


def deduplicate_and_sort(
    recommendations: list[Recommendation],
    limit: int,
) -> list[Recommendation]:
    """
    1. Remove conflicting recommendations (keep higher-scored one per conflict pair).
    2. Sort by score descending.
    3. Truncate to *limit*.
    """
    # Build action → recommendation map (highest-scored wins)
    action_map: dict[RecommendationAction, Recommendation] = {}
    for rec in sorted(recommendations, key=lambda r: r.score, reverse=True):
        action_map[rec.action] = action_map.get(rec.action) or rec

    # Resolve conflict pairs
    survivors: dict[str, Recommendation] = {r.id: r for r in action_map.values()}
    for a1, a2 in _CONFLICT_PAIRS:
        if a1 in action_map and a2 in action_map:
            loser = (
                action_map[a2]
                if action_map[a1].score >= action_map[a2].score
                else action_map[a1]
            )
            survivors.pop(loser.id, None)

    # Sort and cap
    ranked = sorted(survivors.values(), key=lambda r: r.score, reverse=True)
    return ranked[:limit]
