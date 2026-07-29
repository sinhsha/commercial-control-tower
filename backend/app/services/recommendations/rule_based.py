"""
Rule-Based Commercial Recommendation Engine.

This module implements all six rules described in the specification.
Each rule is a private method that receives the same context object
(RecommendationContext) and returns zero or more Recommendation objects.

Rules
─────
1. HIGH-DEMAND PRICING RULE        – occupancy ≥ 85%, competitor ADR support
2. VERY-HIGH-DEMAND RESTRICTION    – occupancy ≥ 92%, high booking pace
3. LOW-DEMAND RULE                 – occupancy < 55%, low pace, no strong event
4. PREMIUM-INVENTORY RULE          – occupancy > 88%, premium rooms scarce
5. EVENT-PACKAGE RULE              – convention/concert/sports/festival nearby
6. OPERATIONAL-PRESSURE RULE       – occupancy > 95%, high expected arrivals

Guardrails (from config, not hardcoded)
───────────────────────────────────────
    maximum_rate_increase_pct         (default 12.0)
    maximum_rate_decrease_pct         (default 10.0)
    minimum_recommended_rate          (default 79.0)
    maximum_recommended_rate          (default 999.0)
    minimum_confidence_for_high_prio  (not used directly; handled by scoring)
    maximum_recommendations_per_hotel (default 10)

To replace with an optimiser
─────────────────────────────
Implement RecommendationService with the same interface.  The API,
schemas, and frontend consume RecommendationResponse – they do not care
which engine produced it.  See base.py for the extension-point docstring.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

from app.models.demand_event import DemandEvent
from app.repositories.event_repository import EventRepository
from app.repositories.hotel_repository import HotelRepository
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.events import AdjustedForecastDay
from app.schemas.forecast import ForecastPoint
from app.schemas.recommendations import (
    MarketSignals,
    Recommendation,
    RecommendationAction,
    RecommendationCategory,
    RecommendationConfidence,
    RecommendationResponse,
    RecommendationStatus,
    RecommendationSummary,
    ReasonCode,
)
from app.services.event_engine.base import EventEngineService
from app.services.forecasting.base import ForecastService
from app.services.market_signals.base import MarketSignalService
from app.services.recommendations.base import RecommendationService
from app.services.recommendations.scoring import (
    assign_priority,
    compute_score,
    deduplicate_and_sort,
)

logger = logging.getLogger(__name__)

# ── Guardrail defaults (overridden by Settings when injected) ─────────────────

_DEFAULT_MAX_RATE_INCREASE_PCT: float = 12.0
_DEFAULT_MAX_RATE_DECREASE_PCT: float = 10.0
_DEFAULT_MIN_RATE: float = 79.0
_DEFAULT_MAX_RATE: float = 999.0
_DEFAULT_MAX_RECOMMENDATIONS: int = 10
_HISTORY_WINDOW: int = 90

# Demand-event types that qualify for the event-package rule
_PACKAGE_EVENT_TYPES = frozenset(
    {"convention", "concert", "sports", "local_festival", "holiday", "cruise_arrival"}
)

# ── Internal context object ───────────────────────────────────────────────────


@dataclass
class _Context:
    hotel_id: str
    as_of: date
    horizon_days: int
    total_rooms: int
    current_adr: float
    current_occupancy: float
    current_revpar: float
    baseline_points: list[ForecastPoint]
    adjusted_days: list[AdjustedForecastDay]
    events: list[DemandEvent]
    signals: MarketSignals
    forecast_model: str
    adjustment_model: str
    # Guardrails
    max_rate_increase_pct: float = _DEFAULT_MAX_RATE_INCREASE_PCT
    max_rate_decrease_pct: float = _DEFAULT_MAX_RATE_DECREASE_PCT
    min_rate: float = _DEFAULT_MIN_RATE
    max_rate: float = _DEFAULT_MAX_RATE
    max_recommendations: int = _DEFAULT_MAX_RECOMMENDATIONS
    # Sequence counter for stable IDs
    _seq: int = field(default=0, init=False)

    def next_seq(self, category: RecommendationCategory) -> str:
        self._seq += 1
        return f"REC-{self.hotel_id[:8]}-{self.as_of.isoformat().replace('-', '')}-{category.value.upper()}-{self._seq:03d}"

    @property
    def avg_adjusted_occupancy(self) -> float:
        """Mean adjusted occupancy across the forecast horizon."""
        if not self.adjusted_days:
            return self.current_occupancy
        return sum(d.adjusted for d in self.adjusted_days) / len(self.adjusted_days)

    @property
    def peak_adjusted_occupancy(self) -> float:
        if not self.adjusted_days:
            return self.current_occupancy
        return max(d.adjusted for d in self.adjusted_days)

    @property
    def avg_uplift(self) -> float:
        if not self.adjusted_days:
            return 0.0
        return sum(d.uplift for d in self.adjusted_days) / len(self.adjusted_days)

    @property
    def has_strong_event(self) -> bool:
        """True if any active event has high impact_strength (≥ 0.7)."""
        return any(e.impact_strength >= 0.7 for e in self.events)

    def active_package_events(self) -> list[DemandEvent]:
        return [e for e in self.events if e.event_type in _PACKAGE_EVENT_TYPES]

    def high_demand_days(self, threshold: float = 85.0) -> list[AdjustedForecastDay]:
        return [d for d in self.adjusted_days if d.adjusted >= threshold]

    def consecutive_high_demand_nights(self, threshold: float = 92.0) -> int:
        """Return the longest consecutive run of nights with adjusted occ ≥ threshold."""
        best = 0
        current = 0
        for d in self.adjusted_days:
            if d.adjusted >= threshold:
                current += 1
                best = max(best, current)
            else:
                current = 0
        return best


# ── Main service ──────────────────────────────────────────────────────────────


class RuleBasedRecommendationService(RecommendationService):
    """
    Deterministic rule-based commercial recommendation engine.

    Consumes existing services through their interfaces – no logic is
    duplicated from ForecastService or EventEngineService.

    Constructor parameters follow the project's DI pattern.
    """

    recommendation_model: str = "Rule Based Commercial Engine"

    def __init__(
        self,
        hotel_repo: HotelRepository,
        metrics_repo: MetricsRepository,
        event_repo: EventRepository,
        forecast_svc: ForecastService,
        event_engine_svc: EventEngineService,
        market_signal_svc: MarketSignalService,
    ) -> None:
        self._hotel_repo = hotel_repo
        self._metrics_repo = metrics_repo
        self._event_repo = event_repo
        self._forecast_svc = forecast_svc
        self._event_engine_svc = event_engine_svc
        self._market_signal_svc = market_signal_svc

    # ── Public interface ──────────────────────────────────────────────────────

    async def generate_recommendations(
        self,
        hotel_id: str,
        as_of: date,
        horizon_days: int = 14,
    ) -> RecommendationResponse:
        ctx = await self._build_context(hotel_id, as_of, horizon_days)

        raw: list[Recommendation] = []
        for rule in [
            self._rule_high_demand_pricing,
            self._rule_very_high_demand_restriction,
            self._rule_low_demand,
            self._rule_premium_inventory,
            self._rule_event_package,
            self._rule_operational_pressure,
        ]:
            raw.extend(rule(ctx))

        ranked = deduplicate_and_sort(raw, ctx.max_recommendations)

        return RecommendationResponse(
            hotel_id=hotel_id,
            generated_at=datetime.now(timezone.utc),
            forecast_model=ctx.forecast_model,
            adjustment_model=ctx.adjustment_model,
            recommendation_model=self.recommendation_model,
            summary=self._build_summary(ranked),
            recommendations=ranked,
        )

    # ── Context builder ───────────────────────────────────────────────────────

    async def _build_context(
        self, hotel_id: str, as_of: date, horizon_days: int
    ) -> _Context:
        hotel = await self._hotel_repo.get_by_id(hotel_id)
        if hotel is None:
            raise ValueError(f"Hotel {hotel_id!r} not found")

        # Latest metrics (fallback to as_of)
        metrics = await self._metrics_repo.get_by_hotel_and_date(hotel_id, as_of)
        if metrics is None:
            metrics = await self._metrics_repo.get_latest(hotel_id)
        if metrics is None:
            raise ValueError(f"No metrics available for hotel {hotel_id!r}")

        # History for baseline forecast
        history_start = as_of - timedelta(days=_HISTORY_WINDOW - 1)
        history_records = await self._metrics_repo.get_range(hotel_id, history_start, as_of)
        history = [(r.date, r.occupancy_pct) for r in history_records]

        baseline_points: list[ForecastPoint] = []
        adjusted_days: list[AdjustedForecastDay] = []
        forecast_model = self._forecast_svc.model_name
        adjustment_model = self._event_engine_svc.engine_name

        if len(history) >= self._forecast_svc.min_history_days:
            baseline_points = await self._forecast_svc.forecast(
                hotel_id=hotel_id,
                history=history,
                horizon=horizon_days,
                origin=as_of,
            )
            forecast_end = as_of + timedelta(days=horizon_days)
            events = await self._event_repo.get_overlapping(
                hotel_id, as_of + timedelta(days=1), forecast_end
            )
            adjusted_days = self._event_engine_svc.apply(
                hotel_id=hotel_id,
                hotel_total_rooms=hotel.total_rooms,
                forecast_origin_date=as_of,
                baseline=baseline_points,
                events=events,
            )
        else:
            events = await self._event_repo.get_active_for_hotel(hotel_id)

        signals = await self._market_signal_svc.get_signals(hotel_id, hotel_adr=metrics.adr)

        return _Context(
            hotel_id=hotel_id,
            as_of=as_of,
            horizon_days=horizon_days,
            total_rooms=hotel.total_rooms,
            current_adr=metrics.adr,
            current_occupancy=metrics.occupancy_pct,
            current_revpar=metrics.revpar,
            baseline_points=baseline_points,
            adjusted_days=adjusted_days,
            events=events,
            signals=signals,
            forecast_model=forecast_model,
            adjustment_model=adjustment_model,
        )

    # ── Rule 1: High-Demand Pricing ───────────────────────────────────────────

    def _rule_high_demand_pricing(self, ctx: _Context) -> list[Recommendation]:
        """
        When adjusted occupancy ≥ 85% AND demand uplift is positive AND
        competitor ADR ≥ hotel ADR → recommend a guarded rate increase.
        """
        recs: list[Recommendation] = []
        high_demand_days = ctx.high_demand_days(threshold=85.0)

        if not high_demand_days:
            return recs
        if ctx.avg_uplift <= 0:
            return recs
        if ctx.signals.competitor_adr < ctx.current_adr:
            return recs

        # Scale increase 5–12% based on peak occupancy
        peak_occ = max(d.adjusted for d in high_demand_days)
        raw_increase_pct = 5.0 + ((peak_occ - 85.0) / 15.0) * 7.0  # 5% at 85%, 12% at 100%
        raw_increase_pct = min(raw_increase_pct, ctx.max_rate_increase_pct)

        new_rate = ctx.current_adr * (1 + raw_increase_pct / 100.0)
        new_rate = min(new_rate, ctx.max_rate)
        new_rate = max(new_rate, ctx.min_rate)
        applied_pct = round((new_rate - ctx.current_adr) / ctx.current_adr * 100, 1)

        # Impact estimate: rate delta × avg occupied rooms × affected nights
        forecast_occ_ratio = peak_occ / 100.0
        occupied_rooms_est = round(ctx.total_rooms * forecast_occ_ratio)
        nights = len(high_demand_days)
        revenue_impact = round((new_rate - ctx.current_adr) * occupied_rooms_est * nights, 0)

        confidence = (
            RecommendationConfidence.high
            if ctx.has_strong_event
            else RecommendationConfidence.medium
        )
        score = compute_score(
            expected_revenue_impact=revenue_impact,
            confidence=confidence,
            effective_start=high_demand_days[0].date,
            as_of=ctx.as_of,
            adjusted_occupancy=peak_occ,
            has_active_event=ctx.has_strong_event,
        )
        priority = assign_priority(score, confidence)

        supporting = [
            f"Adjusted occupancy forecast peak: {peak_occ:.1f}%",
            f"Demand uplift: +{ctx.avg_uplift:.1f} pp avg over horizon",
            f"Competitor ADR: ${ctx.signals.competitor_adr:.0f}",
            f"Current ADR: ${ctx.current_adr:.0f}",
            f"Rate increase {applied_pct}% (capped at {ctx.max_rate_increase_pct}%)",
        ]
        risk_flags: list[str] = []
        if applied_pct < raw_increase_pct:
            risk_flags.append(
                f"Increase capped at configured guardrail ({ctx.max_rate_increase_pct}%)"
            )
        if new_rate >= ctx.max_rate:
            risk_flags.append(f"Rate capped at configured maximum (${ctx.max_rate:.0f})")

        reason_codes = [ReasonCode.high_forecast_occupancy, ReasonCode.competitor_rate_support]
        if ctx.has_strong_event:
            reason_codes.append(ReasonCode.event_demand)

        recs.append(
            Recommendation(
                id=ctx.next_seq(RecommendationCategory.pricing),
                hotel_id=ctx.hotel_id,
                category=RecommendationCategory.pricing,
                action=RecommendationAction.increase_rate,
                title=f"Increase flexible rate by {applied_pct}%",
                summary=(
                    f"Demand is forecast to exceed {int(peak_occ)}% occupancy over "
                    f"{nights} night{'s' if nights != 1 else ''}. "
                    f"Competitor ADR (${ctx.signals.competitor_adr:.0f}) supports the increase."
                ),
                effective_start_date=high_demand_days[0].date,
                effective_end_date=high_demand_days[-1].date,
                current_value=round(ctx.current_adr, 2),
                recommended_value=round(new_rate, 2),
                unit="USD",
                score=score,
                priority=priority,
                confidence=confidence,
                expected_revenue_impact=revenue_impact,
                expected_occupancy_impact=0.0,
                reason_codes=reason_codes,
                supporting_factors=supporting,
                risk_flags=risk_flags,
                status=RecommendationStatus.proposed,
            )
        )
        return recs

    # ── Rule 2: Very-High-Demand Restrictions ─────────────────────────────────

    def _rule_very_high_demand_restriction(self, ctx: _Context) -> list[Recommendation]:
        """
        When adjusted occupancy ≥ 92% AND booking pace > normal →
        close discounted rates; if ≥ 2 consecutive nights, add MLOS 2.
        """
        recs: list[Recommendation] = []
        very_high_days = ctx.high_demand_days(threshold=92.0)

        if not very_high_days:
            return recs
        if ctx.signals.booking_pace_index <= 1.0:
            return recs

        peak_occ = max(d.adjusted for d in very_high_days)
        confidence = RecommendationConfidence.high if ctx.has_strong_event else RecommendationConfidence.medium

        # Close discounts
        score_disc = compute_score(
            expected_revenue_impact=ctx.current_adr * ctx.total_rooms * 0.05 * len(very_high_days),
            confidence=confidence,
            effective_start=very_high_days[0].date,
            as_of=ctx.as_of,
            adjusted_occupancy=peak_occ,
            has_active_event=ctx.has_strong_event,
        )
        recs.append(
            Recommendation(
                id=ctx.next_seq(RecommendationCategory.restrictions),
                hotel_id=ctx.hotel_id,
                category=RecommendationCategory.restrictions,
                action=RecommendationAction.close_discounted_rates,
                title="Close discounted rate plans",
                summary=(
                    f"Occupancy forecast of {peak_occ:.1f}% with booking pace "
                    f"{ctx.signals.booking_pace_index:.2f}× normal suggests full-rate demand "
                    f"can fill the hotel. Protecting BAR revenue by closing discounts."
                ),
                effective_start_date=very_high_days[0].date,
                effective_end_date=very_high_days[-1].date,
                current_value=None,
                recommended_value=None,
                unit="rate plans",
                score=score_disc,
                priority=assign_priority(score_disc, confidence),
                confidence=confidence,
                expected_revenue_impact=round(
                    ctx.current_adr * ctx.total_rooms * 0.05 * len(very_high_days), 0
                ),
                expected_occupancy_impact=0.0,
                reason_codes=[ReasonCode.very_high_forecast_occupancy, ReasonCode.high_booking_pace],
                supporting_factors=[
                    f"Peak adjusted occupancy: {peak_occ:.1f}%",
                    f"Booking pace index: {ctx.signals.booking_pace_index:.2f}×",
                ],
                risk_flags=[],
                status=RecommendationStatus.proposed,
            )
        )

        # MLOS if ≥ 2 consecutive nights
        consec = ctx.consecutive_high_demand_nights(threshold=92.0)
        if consec >= 2:
            score_mlos = compute_score(
                expected_revenue_impact=ctx.current_adr * ctx.total_rooms * 0.03 * consec,
                confidence=confidence,
                effective_start=very_high_days[0].date,
                as_of=ctx.as_of,
                adjusted_occupancy=peak_occ,
                has_active_event=ctx.has_strong_event,
            )
            recs.append(
                Recommendation(
                    id=ctx.next_seq(RecommendationCategory.restrictions),
                    hotel_id=ctx.hotel_id,
                    category=RecommendationCategory.restrictions,
                    action=RecommendationAction.add_minimum_length_of_stay,
                    title="Add 2-night minimum length of stay",
                    summary=(
                        f"Demand peak spans {consec} consecutive nights at ≥92% occupancy. "
                        f"A MLOS-2 restriction reduces expensive single-night stays and "
                        f"improves total stay revenue."
                    ),
                    effective_start_date=very_high_days[0].date,
                    effective_end_date=very_high_days[-1].date,
                    current_value=1.0,
                    recommended_value=2.0,
                    unit="nights",
                    score=score_mlos,
                    priority=assign_priority(score_mlos, confidence),
                    confidence=confidence,
                    expected_revenue_impact=round(
                        ctx.current_adr * ctx.total_rooms * 0.03 * consec, 0
                    ),
                    expected_occupancy_impact=0.0,
                    reason_codes=[
                        ReasonCode.very_high_forecast_occupancy,
                        ReasonCode.multi_night_demand_peak,
                    ],
                    supporting_factors=[
                        f"{consec} consecutive nights with adjusted occupancy ≥ 92%",
                    ],
                    risk_flags=[],
                    status=RecommendationStatus.proposed,
                )
            )
        return recs

    # ── Rule 3: Low-Demand ────────────────────────────────────────────────────

    def _rule_low_demand(self, ctx: _Context) -> list[Recommendation]:
        """
        When avg adjusted occupancy < 55% AND pace below normal AND no strong event →
        recommend either a modest rate reduction OR hold + launch value-add package.
        We prefer hold + package (avoids rate erosion) unless occupancy is very low (<40%).
        """
        if ctx.avg_adjusted_occupancy >= 55.0:
            return []
        if ctx.signals.booking_pace_index >= 1.0:
            return []
        if ctx.has_strong_event:
            return []

        avg_occ = ctx.avg_adjusted_occupancy

        if avg_occ < 40.0:
            # More aggressive: suggest rate reduction (but no more than configured max)
            decrease_pct = min(
                ctx.max_rate_decrease_pct,
                round((40.0 - avg_occ) / 40.0 * ctx.max_rate_decrease_pct, 1),
            )
            new_rate = max(ctx.current_adr * (1 - decrease_pct / 100.0), ctx.min_rate)
            applied_pct = round((ctx.current_adr - new_rate) / ctx.current_adr * 100, 1)
            occupied_est = round(ctx.total_rooms * avg_occ / 100)
            nights = len(ctx.adjusted_days)
            revenue_impact = round((ctx.current_adr - new_rate) * occupied_est * nights * -1, 0)

            confidence = RecommendationConfidence.medium
            score = compute_score(
                expected_revenue_impact=abs(revenue_impact) * 0.5,  # partial offset via volume
                confidence=confidence,
                effective_start=ctx.adjusted_days[0].date if ctx.adjusted_days else ctx.as_of + timedelta(days=1),
                as_of=ctx.as_of,
                adjusted_occupancy=avg_occ,
                has_active_event=False,
            )
            risk_flags = [f"Rate decrease limited to configured guardrail ({ctx.max_rate_decrease_pct}%)"]
            if new_rate <= ctx.min_rate:
                risk_flags.append(f"Rate floored at minimum (${ctx.min_rate:.0f})")
            return [
                Recommendation(
                    id=ctx.next_seq(RecommendationCategory.pricing),
                    hotel_id=ctx.hotel_id,
                    category=RecommendationCategory.pricing,
                    action=RecommendationAction.reduce_rate,
                    title=f"Reduce flexible rate by {applied_pct}% to stimulate demand",
                    summary=(
                        f"Adjusted occupancy forecast of {avg_occ:.1f}% with booking pace "
                        f"{ctx.signals.booking_pace_index:.2f}× below normal. "
                        f"A controlled rate reduction may recover volume."
                    ),
                    effective_start_date=ctx.adjusted_days[0].date if ctx.adjusted_days else ctx.as_of + timedelta(days=1),
                    effective_end_date=ctx.adjusted_days[-1].date if ctx.adjusted_days else ctx.as_of + timedelta(days=ctx.horizon_days),
                    current_value=round(ctx.current_adr, 2),
                    recommended_value=round(new_rate, 2),
                    unit="USD",
                    score=score,
                    priority=assign_priority(score, confidence),
                    confidence=confidence,
                    expected_revenue_impact=revenue_impact,
                    expected_occupancy_impact=round((55.0 - avg_occ) * 0.3, 1),
                    reason_codes=[ReasonCode.low_forecast_occupancy, ReasonCode.low_booking_pace],
                    supporting_factors=[
                        f"Average adjusted occupancy: {avg_occ:.1f}%",
                        f"Booking pace index: {ctx.signals.booking_pace_index:.2f}×",
                    ],
                    risk_flags=risk_flags,
                    status=RecommendationStatus.proposed,
                )
            ]
        else:
            # Softer: hold rate, launch value-add package
            confidence = RecommendationConfidence.medium
            eligible_guests = round(ctx.total_rooms * avg_occ / 100)
            pkg_revenue = round(eligible_guests * 0.20 * 35.0 * len(ctx.adjusted_days), 0)
            score = compute_score(
                expected_revenue_impact=pkg_revenue,
                confidence=confidence,
                effective_start=ctx.adjusted_days[0].date if ctx.adjusted_days else ctx.as_of + timedelta(days=1),
                as_of=ctx.as_of,
                adjusted_occupancy=avg_occ,
                has_active_event=False,
            )
            return [
                Recommendation(
                    id=ctx.next_seq(RecommendationCategory.package),
                    hotel_id=ctx.hotel_id,
                    category=RecommendationCategory.package,
                    action=RecommendationAction.launch_breakfast_package,
                    title="Launch breakfast package to add value without rate erosion",
                    summary=(
                        f"Adjusted occupancy of {avg_occ:.1f}% is below target. "
                        f"A breakfast-inclusive package maintains rate integrity while "
                        f"improving perceived value and conversion."
                    ),
                    effective_start_date=ctx.adjusted_days[0].date if ctx.adjusted_days else ctx.as_of + timedelta(days=1),
                    effective_end_date=ctx.adjusted_days[-1].date if ctx.adjusted_days else ctx.as_of + timedelta(days=ctx.horizon_days),
                    current_value=None,
                    recommended_value=None,
                    unit="package",
                    score=score,
                    priority=assign_priority(score, confidence),
                    confidence=confidence,
                    expected_revenue_impact=pkg_revenue,
                    expected_occupancy_impact=round((55.0 - avg_occ) * 0.2, 1),
                    reason_codes=[
                        ReasonCode.low_forecast_occupancy,
                        ReasonCode.value_add_opportunity,
                    ],
                    supporting_factors=[
                        f"Average adjusted occupancy: {avg_occ:.1f}%",
                        f"Estimated eligible guests: {eligible_guests}",
                        "Conversion rate estimate: 20% @ $35 margin/guest",
                    ],
                    risk_flags=[],
                    status=RecommendationStatus.proposed,
                )
            ]

    # ── Rule 4: Premium-Inventory Protection ──────────────────────────────────

    def _rule_premium_inventory(self, ctx: _Context) -> list[Recommendation]:
        """
        When adjusted occupancy > 88% AND premium rooms scarce (<15) →
        protect premium inventory, restrict comps, open paid upgrades.
        """
        recs: list[Recommendation] = []
        high_days = ctx.high_demand_days(threshold=88.0)
        if not high_days:
            return recs
        if ctx.signals.premium_rooms_available >= 15:
            return recs

        peak_occ = max(d.adjusted for d in high_days)
        confidence = RecommendationConfidence.high if peak_occ >= 92 else RecommendationConfidence.medium
        nights = len(high_days)

        # Protect premium inventory
        protect_revenue = round(ctx.signals.premium_rooms_available * 80.0 * nights, 0)
        score_protect = compute_score(
            expected_revenue_impact=protect_revenue,
            confidence=confidence,
            effective_start=high_days[0].date,
            as_of=ctx.as_of,
            adjusted_occupancy=peak_occ,
            has_active_event=ctx.has_strong_event,
        )
        recs.append(
            Recommendation(
                id=ctx.next_seq(RecommendationCategory.inventory),
                hotel_id=ctx.hotel_id,
                category=RecommendationCategory.inventory,
                action=RecommendationAction.protect_premium_inventory,
                title=f"Protect {ctx.signals.premium_rooms_available} premium rooms from early allocation",
                summary=(
                    f"Only {ctx.signals.premium_rooms_available} premium rooms remain available. "
                    f"Forecast occupancy of {peak_occ:.1f}% supports holding them for "
                    f"higher-value last-minute bookings."
                ),
                effective_start_date=high_days[0].date,
                effective_end_date=high_days[-1].date,
                current_value=float(ctx.signals.premium_rooms_available),
                recommended_value=float(ctx.signals.premium_rooms_available),
                unit="rooms",
                score=score_protect,
                priority=assign_priority(score_protect, confidence),
                confidence=confidence,
                expected_revenue_impact=protect_revenue,
                expected_occupancy_impact=0.0,
                reason_codes=[ReasonCode.premium_inventory_scarce, ReasonCode.high_forecast_occupancy],
                supporting_factors=[
                    f"Premium rooms available: {ctx.signals.premium_rooms_available}",
                    f"Peak adjusted occupancy: {peak_occ:.1f}%",
                ],
                risk_flags=[],
                status=RecommendationStatus.proposed,
            )
        )

        # Restrict complimentary upgrades
        score_comp = compute_score(
            expected_revenue_impact=protect_revenue * 0.6,
            confidence=confidence,
            effective_start=high_days[0].date,
            as_of=ctx.as_of,
            adjusted_occupancy=peak_occ,
            has_active_event=ctx.has_strong_event,
        )
        recs.append(
            Recommendation(
                id=ctx.next_seq(RecommendationCategory.upgrade),
                hotel_id=ctx.hotel_id,
                category=RecommendationCategory.upgrade,
                action=RecommendationAction.restrict_complimentary_upgrades,
                title="Restrict complimentary upgrades – push paid upgrade path",
                summary=(
                    f"With only {ctx.signals.premium_rooms_available} premium rooms "
                    f"and {peak_occ:.1f}% forecast occupancy, complimentary upgrades "
                    f"displace paid revenue. Redirect guests to a paid-upgrade offer."
                ),
                effective_start_date=high_days[0].date,
                effective_end_date=high_days[-1].date,
                current_value=None,
                recommended_value=None,
                unit="policy",
                score=score_comp,
                priority=assign_priority(score_comp, confidence),
                confidence=confidence,
                expected_revenue_impact=round(protect_revenue * 0.6, 0),
                expected_occupancy_impact=0.0,
                reason_codes=[ReasonCode.premium_inventory_scarce],
                supporting_factors=[f"Premium rooms available: {ctx.signals.premium_rooms_available}"],
                risk_flags=[],
                status=RecommendationStatus.proposed,
            )
        )

        # Open paid upgrades
        upgrade_revenue = round(ctx.signals.premium_rooms_available * 55.0 * nights * 0.35, 0)
        score_upg = compute_score(
            expected_revenue_impact=upgrade_revenue,
            confidence=confidence,
            effective_start=high_days[0].date,
            as_of=ctx.as_of,
            adjusted_occupancy=peak_occ,
            has_active_event=ctx.has_strong_event,
        )
        recs.append(
            Recommendation(
                id=ctx.next_seq(RecommendationCategory.upgrade),
                hotel_id=ctx.hotel_id,
                category=RecommendationCategory.upgrade,
                action=RecommendationAction.open_paid_upgrades,
                title="Open paid upgrade offers for premium rooms",
                summary=(
                    f"High demand period creates upgrade revenue opportunity. "
                    f"Estimated {upgrade_revenue:.0f} USD from paid upgrades "
                    f"at 35% conversion on {ctx.signals.premium_rooms_available} premium rooms."
                ),
                effective_start_date=high_days[0].date,
                effective_end_date=high_days[-1].date,
                current_value=None,
                recommended_value=55.0,
                unit="USD/upgrade",
                score=score_upg,
                priority=assign_priority(score_upg, confidence),
                confidence=confidence,
                expected_revenue_impact=upgrade_revenue,
                expected_occupancy_impact=0.0,
                reason_codes=[ReasonCode.premium_inventory_scarce, ReasonCode.high_forecast_occupancy],
                supporting_factors=[
                    f"Premium rooms: {ctx.signals.premium_rooms_available}",
                    "Conversion estimate: 35% @ $55/upgrade/night",
                ],
                risk_flags=[],
                status=RecommendationStatus.proposed,
            )
        )
        return recs

    # ── Rule 5: Event-Package ─────────────────────────────────────────────────

    def _rule_event_package(self, ctx: _Context) -> list[Recommendation]:
        """
        When a convention / concert / sports / festival event is active nearby →
        recommend an event-linked package (breakfast, parking, late checkout, transport).
        """
        pkg_events = ctx.active_package_events()
        if not pkg_events:
            return []

        recs: list[Recommendation] = []
        for event in pkg_events[:2]:  # cap to avoid flooding
            eligible_guests = round(ctx.total_rooms * 0.75)
            pkg_revenue = round(eligible_guests * 0.25 * 45.0, 0)
            confidence = (
                RecommendationConfidence.high
                if event.confidence >= 0.8
                else RecommendationConfidence.medium
            )
            start = max(event.start_date, ctx.as_of + timedelta(days=1))
            end = event.end_date
            if start > end:
                continue

            score = compute_score(
                expected_revenue_impact=pkg_revenue,
                confidence=confidence,
                effective_start=start,
                as_of=ctx.as_of,
                adjusted_occupancy=ctx.avg_adjusted_occupancy,
                has_active_event=True,
            )

            # Choose package type based on event type
            if event.event_type in {"convention", "sports"}:
                action = RecommendationAction.launch_parking_package
                pkg_label = "Parking Package"
            elif event.event_type in {"concert", "local_festival"}:
                action = RecommendationAction.promote_late_checkout
                pkg_label = "Late Checkout Offer"
            else:
                action = RecommendationAction.launch_event_package
                pkg_label = "Event Package"

            recs.append(
                Recommendation(
                    id=ctx.next_seq(RecommendationCategory.package),
                    hotel_id=ctx.hotel_id,
                    category=RecommendationCategory.package,
                    action=action,
                    title=f"Launch {pkg_label} linked to {event.name}",
                    summary=(
                        f"{event.name} ({event.event_type}, {event.expected_attendance:,} attendees) "
                        f"is expected {event.distance_miles:.1f} miles away. "
                        f"A targeted package improves conversion and ancillary revenue."
                    ),
                    effective_start_date=start,
                    effective_end_date=end,
                    current_value=None,
                    recommended_value=45.0,
                    unit="USD/package",
                    score=score,
                    priority=assign_priority(score, confidence),
                    confidence=confidence,
                    expected_revenue_impact=pkg_revenue,
                    expected_occupancy_impact=round((75.0 - ctx.avg_adjusted_occupancy) * 0.1, 1) if ctx.avg_adjusted_occupancy < 75 else 0.0,
                    reason_codes=[ReasonCode.event_demand, ReasonCode.value_add_opportunity],
                    supporting_factors=[
                        f"Event: {event.name}",
                        f"Type: {event.event_type}",
                        f"Attendance: {event.expected_attendance:,}",
                        f"Distance: {event.distance_miles:.1f} miles",
                        f"Event confidence: {event.confidence:.0%}",
                        "Conversion estimate: 25% @ $45 margin",
                    ],
                    risk_flags=[],
                    status=RecommendationStatus.proposed,
                )
            )
        return recs

    # ── Rule 6: Operational Pressure ─────────────────────────────────────────

    def _rule_operational_pressure(self, ctx: _Context) -> list[Recommendation]:
        """
        When adjusted occupancy > 95% AND expected arrivals are high →
        alert front desk, housekeeping, and revenue manager.
        """
        recs: list[Recommendation] = []
        critical_days = ctx.high_demand_days(threshold=95.0)
        if not critical_days:
            return recs
        if ctx.signals.expected_arrivals < 70:
            return recs

        peak_occ = max(d.adjusted for d in critical_days)
        confidence = RecommendationConfidence.high
        base_score = compute_score(
            expected_revenue_impact=0.0,
            confidence=confidence,
            effective_start=critical_days[0].date,
            as_of=ctx.as_of,
            adjusted_occupancy=peak_occ,
            has_active_event=ctx.has_strong_event,
        )

        alerts = [
            (
                RecommendationAction.alert_front_desk,
                "Alert front desk: high arrival volume expected",
                f"Expected {ctx.signals.expected_arrivals} arrivals with {peak_occ:.1f}% occupancy. "
                f"Ensure staffing and pre-registration workflows are ready.",
            ),
            (
                RecommendationAction.alert_housekeeping,
                "Alert housekeeping: full turnover readiness required",
                f"{peak_occ:.1f}% occupancy requires full room readiness by standard check-in time. "
                f"Prioritise early checkouts and stagger departure inspections.",
            ),
            (
                RecommendationAction.alert_revenue_manager,
                "Revenue manager: monitor walk-in rate and overbooking buffer",
                f"Near-sell-out ({peak_occ:.1f}%) with {ctx.signals.expected_arrivals} arrivals. "
                f"Review overbooking policy and last-room-availability rates.",
            ),
        ]

        for action, title, summary in alerts:
            recs.append(
                Recommendation(
                    id=ctx.next_seq(RecommendationCategory.operational),
                    hotel_id=ctx.hotel_id,
                    category=RecommendationCategory.operational,
                    action=action,
                    title=title,
                    summary=summary,
                    effective_start_date=critical_days[0].date,
                    effective_end_date=critical_days[-1].date,
                    current_value=None,
                    recommended_value=None,
                    unit="alert",
                    score=base_score - 2.0,
                    priority=assign_priority(base_score - 2.0, confidence),
                    confidence=confidence,
                    expected_revenue_impact=0.0,
                    expected_occupancy_impact=0.0,
                    reason_codes=[ReasonCode.operational_pressure, ReasonCode.very_high_forecast_occupancy],
                    supporting_factors=[
                        f"Peak adjusted occupancy: {peak_occ:.1f}%",
                        f"Expected arrivals: {ctx.signals.expected_arrivals}",
                    ],
                    risk_flags=[],
                    status=RecommendationStatus.proposed,
                )
            )
        return recs

    # ── Summary builder ───────────────────────────────────────────────────────

    @staticmethod
    def _build_summary(recommendations: list[Recommendation]) -> RecommendationSummary:
        from app.schemas.recommendations import RecommendationPriority

        counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        total_revenue = 0.0
        for rec in recommendations:
            counts[rec.priority.value] += 1
            total_revenue += rec.expected_revenue_impact

        return RecommendationSummary(
            total=len(recommendations),
            critical=counts["critical"],
            high=counts["high"],
            medium=counts["medium"],
            low=counts["low"],
            estimated_revenue_opportunity=round(total_revenue, 0),
        )
