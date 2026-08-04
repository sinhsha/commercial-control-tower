"""
Rule-based implementation of RoomPricingService.

Uses deterministic pricing rules, demand/scarcity/competitor multipliers,
and guardrails to produce per-room-type pricing recommendations.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Final

from app.repositories.hotel_repository import HotelRepository
from app.repositories.metrics_repository import MetricsRepository
from app.repositories.event_repository import EventRepository
from app.repositories.room_type_repository import RoomTypeRepository
from app.services.forecasting.base import ForecastService
from app.services.market_signals.base import MarketSignalService
from app.services.room_pricing.base import RoomPricingService
from app.services.room_pricing.pricing_rules import (
    compute_recommended_price,
    competitor_multiplier,
    demand_multiplier,
    enforce_room_hierarchy,
    los_recommendation,
    protection_status,
    scarcity_multiplier,
)
from app.schemas.room_pricing import (
    InventoryResponse,
    InventoryStatus,
    RoomCalendarDay,
    RoomCalendarResponse,
    RoomPricingResponse,
    RoomTypePricingRecommendation,
    RoomTypeCalendar,
)

logger = logging.getLogger(__name__)

_CONFIDENCE_HIGH_THRESHOLD = 0.10   # price change < 10% → high confidence
_CONFIDENCE_MED_THRESHOLD  = 0.20   # price change < 20% → medium confidence
_HISTORY_WINDOW: Final = 60          # days of history to pass to forecast service


class RuleBasedRoomPricingService(RoomPricingService):
    """
    Deterministic rule-based room pricing and inventory optimization.

    Swap by changing get_room_pricing_service() in dependencies.py.
    """

    def __init__(
        self,
        hotel_repo: HotelRepository,
        metrics_repo: MetricsRepository,
        event_repo: EventRepository,
        forecast_svc: ForecastService,
        market_svc: MarketSignalService,
        room_repo: RoomTypeRepository,
    ) -> None:
        self._hotel_repo = hotel_repo
        self._metrics_repo = metrics_repo
        self._event_repo = event_repo
        self._forecast_svc = forecast_svc
        self._market_svc = market_svc
        self._room_repo = room_repo

    # ── helpers ───────────────────────────────────────────────────────────────

    def _confidence_label(self, price_change_pct: float) -> str:
        abs_pct = abs(price_change_pct)
        if abs_pct < _CONFIDENCE_HIGH_THRESHOLD * 100:
            return "high"
        if abs_pct < _CONFIDENCE_MED_THRESHOLD * 100:
            return "medium"
        return "low"

    def _build_reason_codes(
        self,
        demand_mult: float,
        scarcity_mult: float,
        comp_mult: float,
    ) -> list[str]:
        codes: list[str] = []
        if demand_mult > 1.0:
            codes.append("high_forecast_occupancy")
        elif demand_mult < 1.0:
            codes.append("low_forecast_occupancy")
        if scarcity_mult > 1.0:
            codes.append("room_scarcity")
        elif scarcity_mult < 1.0:
            codes.append("ample_inventory")
        if comp_mult > 1.0:
            codes.append("competitor_rate_support")
        elif comp_mult < 1.0:
            codes.append("competitor_rate_pressure")
        return codes

    def _build_supporting_factors(
        self,
        forecast_occ: float,
        comp_adr: float,
        hotel_adr: float,
        active_events: list,
    ) -> list[str]:
        factors: list[str] = []
        factors.append(f"Forecast occupancy: {forecast_occ:.1f}%")
        if comp_adr > 0:
            diff = hotel_adr - comp_adr
            factors.append(
                f"Compset ADR: ${comp_adr:.0f} (hotel {'above' if diff >= 0 else 'below'} by ${abs(diff):.0f})"
            )
        if active_events:
            factors.append(f"{len(active_events)} active demand event(s)")
        return factors

    # ── helpers ─────────────────────────────────────────────────────────────
    async def _fetch_forecast_occ(
        self, hotel_id: str, as_of: date, horizon_days: int
    ) -> tuple[float, list]:
        """Return (avg_occupancy_pct, forecast_points_list) for the horizon."""
        history_start = as_of - timedelta(days=_HISTORY_WINDOW - 1)
        history_records = await self._metrics_repo.get_range(hotel_id, history_start, as_of)
        history = [(r.date, r.occupancy_pct) for r in history_records]

        if len(history) < self._forecast_svc.min_history_days:
            # Not enough history — fall back to a neutral occupancy
            return 75.0, []

        points = await self._forecast_svc.forecast(
            hotel_id=hotel_id,
            history=history,
            horizon=horizon_days,
            origin=as_of,
        )
        avg_occ = sum(p.occupancy_pct for p in points) / len(points) if points else 75.0
        return avg_occ, points

    # ── generate_recommendations ──────────────────────────────────────────────

    async def generate_recommendations(
        self,
        hotel_id: str,
        as_of: date,
        horizon_days: int = 14,
    ) -> RoomPricingResponse:

        # Fetch room types
        room_types = await self._room_repo.get_by_hotel(hotel_id)
        if not room_types:
            room_types = []

        # Fetch metrics for current ADR
        latest_metrics = await self._metrics_repo.get_latest(hotel_id)
        current_adr = latest_metrics.adr if latest_metrics else 250.0

        # Fetch events
        events = await self._event_repo.get_active_for_hotel(hotel_id)
        active_events = [
            e for e in events
            if e.start_date <= as_of + timedelta(days=horizon_days)
            and e.end_date >= as_of
        ]

        # Fetch forecast
        forecast_occ, _ = await self._fetch_forecast_occ(hotel_id, as_of, horizon_days)

        # Fetch market signals
        signals = await self._market_svc.get_signals(hotel_id)
        comp_adr = signals.competitor_adr

        # Per multiplier
        d_mult = demand_multiplier(forecast_occ)
        s_mult_overall = scarcity_multiplier(
            sum(r.current_available for r in room_types),
            sum(r.inventory_count for r in room_types),
        )
        c_mult = competitor_multiplier(current_adr, comp_adr)

        recommendations: list[RoomTypePricingRecommendation] = []

        for rt in room_types:
            # Per-room-type scarcity (use room-type specific if available, else overall)
            rt_s_mult = scarcity_multiplier(rt.current_available, rt.inventory_count)

            rec_price, guardrails = compute_recommended_price(
                base_rate=rt.base_rate,
                premium_factor=rt.premium_factor,
                demand_mult=d_mult,
                scarcity_mult=rt_s_mult,
                competitor_mult=c_mult,
                minimum_price=rt.minimum_price,
                maximum_price=rt.maximum_price,
                current_price=rt.current_price,
            )

            price_change_pct = (
                (rec_price - rt.current_price) / rt.current_price * 100
                if rt.current_price > 0
                else 0.0
            )

            reason_codes = self._build_reason_codes(d_mult, rt_s_mult, c_mult)
            supporting_factors = self._build_supporting_factors(
                forecast_occ, comp_adr, current_adr, active_events
            )
            prot_status = protection_status(rt.current_available, rt.inventory_count, forecast_occ)
            los_rec = los_recommendation(forecast_occ, days_out=1)
            conf = self._confidence_label(price_change_pct)

            # Upgrade recommendation: suggest upgrade if >80% sold in this type
            sold = rt.inventory_count - rt.current_available
            sold_pct = sold / rt.inventory_count * 100 if rt.inventory_count > 0 else 0.0
            upgrade_rec: str | None = None
            if sold_pct > 80.0 and rt.room_rank < 8:
                upgrade_rec = "Consider upgrading guests to next tier"

            recommendations.append(
                RoomTypePricingRecommendation(
                    room_type_id=rt.id,
                    code=rt.code,
                    display_name=rt.display_name,
                    room_rank=rt.room_rank,
                    capacity=rt.capacity,
                    inventory_count=rt.inventory_count,
                    current_available=rt.current_available,
                    current_price=rt.current_price,
                    recommended_price=rec_price,
                    price_change_pct=round(price_change_pct, 2),
                    minimum_price=rt.minimum_price,
                    maximum_price=rt.maximum_price,
                    demand_multiplier=d_mult,
                    scarcity_multiplier=rt_s_mult,
                    competitor_multiplier=c_mult,
                    premium_factor=rt.premium_factor,
                    confidence=conf,
                    reason_codes=reason_codes,
                    supporting_factors=supporting_factors,
                    guardrails_applied=guardrails,
                    protection_status=prot_status,
                    upgrade_recommendation=upgrade_rec,
                    los_recommendation=los_rec,
                )
            )

        # Enforce room hierarchy
        recommendations = enforce_room_hierarchy(recommendations)

        # Projected KPIs
        total_inv = sum(rt.inventory_count for rt in room_types)
        projected_adr, proj_occ, proj_revenue, current_revenue = self._compute_projected_kpis(
            recommendations, forecast_occ, total_inv
        )
        proj_revpar = projected_adr * proj_occ / 100.0

        return RoomPricingResponse(
            hotel_id=hotel_id,
            as_of_date=as_of,
            forecast_occupancy_pct=round(forecast_occ, 2),
            competitor_adr=round(comp_adr, 2),
            active_events=[
                {"id": e.id, "name": e.name, "event_type": e.event_type}
                for e in active_events
            ],
            recommendations=recommendations,
            projected_adr=round(projected_adr, 2),
            projected_revpar=round(proj_revpar, 2),
            projected_room_revenue=round(proj_revenue, 2),
            projected_occupancy_pct=round(proj_occ, 2),
            projected_revenue_opportunity=round(proj_revenue - current_revenue, 2),
        )

    def _compute_projected_kpis(
        self,
        recommendations: list[RoomTypePricingRecommendation],
        forecast_occ: float,
        total_inv: int,
    ) -> tuple[float, float, float, float]:
        """Returns (projected_adr, projected_occ_pct, projected_revenue, current_revenue)."""
        if not recommendations:
            return 0.0, 0.0, 0.0, 0.0

        occ_fraction = forecast_occ / 100.0
        total_revenue = 0.0
        total_current_revenue = 0.0
        total_sold = 0

        for rec in recommendations:
            sold_estimate = round(rec.inventory_count * occ_fraction)
            total_revenue += rec.recommended_price * sold_estimate
            total_current_revenue += rec.current_price * sold_estimate
            total_sold += sold_estimate

        projected_adr = total_revenue / total_sold if total_sold > 0 else 0.0
        projected_occ = total_sold / total_inv * 100.0 if total_inv > 0 else 0.0
        return projected_adr, projected_occ, total_revenue, total_current_revenue

    # ── get_calendar ──────────────────────────────────────────────────────────

    async def get_calendar(
        self,
        hotel_id: str,
        as_of: date,
        horizon_days: int = 14,
    ) -> RoomCalendarResponse:

        room_types = await self._room_repo.get_by_hotel(hotel_id)
        signals = await self._market_svc.get_signals(hotel_id)
        comp_adr = signals.competitor_adr

        latest_metrics = await self._metrics_repo.get_latest(hotel_id)
        current_adr = latest_metrics.adr if latest_metrics else 250.0

        _, forecast_points = await self._fetch_forecast_occ(hotel_id, as_of, horizon_days)

        # Build a dict date → occupancy for each forecast day
        occ_by_date: dict[date, float] = {}
        for pt in forecast_points:
            occ_by_date[pt.forecast_date] = pt.occupancy_pct

        room_calendars: list[RoomTypeCalendar] = []

        for rt in room_types:
            days: list[RoomCalendarDay] = []
            for day_offset in range(1, horizon_days + 1):
                target_date = as_of + timedelta(days=day_offset)
                occ = occ_by_date.get(target_date, 75.0)

                d_mult = demand_multiplier(occ)
                s_mult = scarcity_multiplier(rt.current_available, rt.inventory_count)
                c_mult = competitor_multiplier(current_adr, comp_adr)

                rec_price, _ = compute_recommended_price(
                    base_rate=rt.base_rate,
                    premium_factor=rt.premium_factor,
                    demand_mult=d_mult,
                    scarcity_mult=s_mult,
                    competitor_mult=c_mult,
                    minimum_price=rt.minimum_price,
                    maximum_price=rt.maximum_price,
                    current_price=rt.current_price,
                )

                price_change_pct = (
                    (rec_price - rt.current_price) / rt.current_price * 100
                    if rt.current_price > 0
                    else 0.0
                )
                conf = self._confidence_label(price_change_pct)
                prot = protection_status(rt.current_available, rt.inventory_count, occ)

                days.append(
                    RoomCalendarDay(
                        date=target_date,
                        recommended_price=rec_price,
                        current_price=rt.current_price,
                        price_change_pct=round(price_change_pct, 2),
                        confidence=conf,
                        forecast_occupancy_pct=round(occ, 2),
                        protection_status=prot,
                    )
                )

            room_calendars.append(
                RoomTypeCalendar(
                    room_type_id=rt.id,
                    code=rt.code,
                    display_name=rt.display_name,
                    room_rank=rt.room_rank,
                    days=days,
                )
            )

        return RoomCalendarResponse(
            hotel_id=hotel_id,
            horizon_days=horizon_days,
            room_types=room_calendars,
        )

    # ── get_inventory ─────────────────────────────────────────────────────────

    async def get_inventory(
        self,
        hotel_id: str,
        as_of: date,
    ) -> InventoryResponse:

        room_types = await self._room_repo.get_by_hotel(hotel_id)

        # Fetch current forecast occupancy for protection status
        forecast_occ, _ = await self._fetch_forecast_occ(hotel_id, as_of, horizon_days=1)

        inv_statuses: list[InventoryStatus] = []
        total_rooms = 0
        total_sold = 0
        total_available = 0

        for rt in room_types:
            sold = rt.inventory_count - rt.current_available
            occ_pct = sold / rt.inventory_count * 100.0 if rt.inventory_count > 0 else 0.0
            prot = protection_status(rt.current_available, rt.inventory_count, forecast_occ)
            upgrade_eligible = rt.room_rank < 8 and rt.current_available > 0
            revenue_at_risk = rt.current_price * rt.current_available

            inv_statuses.append(
                InventoryStatus(
                    room_type_id=rt.id,
                    code=rt.code,
                    display_name=rt.display_name,
                    room_rank=rt.room_rank,
                    inventory_count=rt.inventory_count,
                    sold=sold,
                    remaining=rt.current_available,
                    occupancy_pct=round(occ_pct, 2),
                    protection_status=prot,
                    upgrade_eligible=upgrade_eligible,
                    revenue_at_risk=round(revenue_at_risk, 2),
                )
            )

            total_rooms += rt.inventory_count
            total_sold += sold
            total_available += rt.current_available

        overall_occ = total_sold / total_rooms * 100.0 if total_rooms > 0 else 0.0

        return InventoryResponse(
            hotel_id=hotel_id,
            as_of_date=as_of,
            total_rooms=total_rooms,
            total_sold=total_sold,
            total_available=total_available,
            overall_occupancy_pct=round(overall_occ, 2),
            room_types=inv_statuses,
        )
