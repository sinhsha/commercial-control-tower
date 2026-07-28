"""
Rule-based Event Engine implementation.

This service is the composition layer between ForecastService outputs and
EventImpactService per-event uplifts.  Its responsibilities are:

    1. For each forecast date, call EventImpactService.compute_uplift for
       every active event.
    2. Weight each influence by the event's ``confidence`` score.
    3. Sum the weighted uplifts into a single net adjustment.
    4. Shift the 80% confidence band by the same adjustment.
    5. Return one AdjustedForecastDay per baseline point.

The engine intentionally contains no forecasting or ML logic; it only
knows how to *combine* uplift signals.

To replace with an ML-based engine:
    1. Create a new class implementing EventEngineService.
    2. Change get_event_engine_service() in app/core/dependencies.py.
    3. Zero other changes required.
"""
from __future__ import annotations

import logging
from datetime import date

from app.models.demand_event import DemandEvent
from app.schemas.events import AdjustedForecastDay, EventInfluence
from app.schemas.forecast import ForecastPoint
from app.services.event_engine.base import EventEngineService
from app.services.events.base import EventImpactService

logger = logging.getLogger(__name__)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


class RuleBasedEventEngineService(EventEngineService):
    """
    Rule-based event engine.

    Combines EventImpactService uplifts with per-event confidence scores
    to produce a net adjustment for each forecast date.

    Parameters
    ----------
    impact_service:
        The injected EventImpactService used to compute per-event uplifts.
        Defaults to DefaultEventImpactService if None is passed (convenience
        only; prefer explicit injection in tests).
    """

    engine_name: str = "Rule Based Event Engine"

    def __init__(self, impact_service: EventImpactService) -> None:
        self._impact = impact_service

    def apply(
        self,
        hotel_id: str,
        hotel_total_rooms: int,
        forecast_origin_date: date,
        baseline: list[ForecastPoint],
        events: list[DemandEvent],
    ) -> list[AdjustedForecastDay]:
        """
        Apply event signals to the baseline forecast.

        For each forecast date:
            - Compute raw uplift per event via EventImpactService
            - Weight by event.confidence (0.0–1.0)
            - Sum confidence-weighted uplifts
            - Shift the 80% CI bounds by the same net uplift
            - Build AdjustedForecastDay with reasons + full influences

        Returns one AdjustedForecastDay per element in ``baseline``.
        """
        result: list[AdjustedForecastDay] = []

        for bp in baseline:
            days_map: dict[str, int] = {
                e.id: max(0, (e.start_date - forecast_origin_date).days)
                for e in events
            }

            net_uplift = 0.0
            influences: list[EventInfluence] = []

            for event in events:
                influence = self._impact.compute_uplift(
                    forecast_date=bp.forecast_date,
                    event=event,
                    hotel_total_rooms=hotel_total_rooms,
                    days_until_event=days_map[event.id],
                )
                if influence is None:
                    continue

                # Weight the raw uplift by event confidence (0–1)
                weighted_uplift = influence.uplift_points * event.confidence

                # Emit the influence with the confidence-weighted uplift
                influences.append(
                    EventInfluence(
                        event_id=influence.event_id,
                        event_name=influence.event_name,
                        event_type=influence.event_type,
                        uplift_points=round(weighted_uplift, 1),
                        confidence=event.confidence,
                        explanation=influence.explanation,
                    )
                )
                net_uplift += weighted_uplift

            net_uplift = round(net_uplift, 1)
            adjusted_occ = _clamp(bp.occupancy_pct + net_uplift)
            adj_lower = _clamp(bp.lower_bound + net_uplift)
            adj_upper = _clamp(bp.upper_bound + net_uplift)

            reasons = [inf.event_name for inf in influences]

            result.append(
                AdjustedForecastDay(
                    date=bp.forecast_date,
                    baseline=round(bp.occupancy_pct, 1),
                    adjusted=round(adjusted_occ, 1),
                    uplift=net_uplift,
                    confidence_low=round(adj_lower, 1),
                    confidence_high=round(adj_upper, 1),
                    reasons=reasons,
                    influences=influences,
                )
            )

            if net_uplift != 0.0:
                logger.debug(
                    "hotel=%s date=%s baseline=%.1f adjusted=%.1f uplift=%.1f events=%s",
                    hotel_id,
                    bp.forecast_date,
                    bp.occupancy_pct,
                    adjusted_occ,
                    net_uplift,
                    [e.name for e in events if e.start_date <= bp.forecast_date <= e.end_date],
                )

        return result
