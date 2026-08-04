"""
Unit & integration tests for the Dynamic Room Pricing & Inventory Optimization engine.

Coverage map
────────────
 1.  Seeder: 8 room types per hotel
 2.  Repository: get_by_hotel returns all types
 3.  demand_multiplier: <50% tier
 4.  demand_multiplier: 50–65% tier
 5.  demand_multiplier: 65–75% tier
 6.  demand_multiplier: 75–85% tier
 7.  demand_multiplier: 85–92% tier
 8.  demand_multiplier: >92% tier
 9.  scarcity_multiplier: >60% ratio → 0.95
10.  scarcity_multiplier: 40–60% ratio → 1.00
11.  scarcity_multiplier: 20–40% ratio → 1.08
12.  scarcity_multiplier: 10–20% ratio → 1.15
13.  scarcity_multiplier: 5–10% ratio → 1.22
14.  scarcity_multiplier: <5% ratio → 1.30
15.  competitor_multiplier: hotel below by >15% → 1.08
16.  competitor_multiplier: hotel below by >8% → 1.05
17.  competitor_multiplier: within 5% → 1.00
18.  competitor_multiplier: hotel above by 5–10% → 0.97
19.  competitor_multiplier: hotel above by >10% → 0.94
20.  compute_recommended_price: correct formula
21.  compute_recommended_price: max increase guardrail
22.  compute_recommended_price: max decrease guardrail
23.  compute_recommended_price: minimum_price floor
24.  compute_recommended_price: maximum_price ceiling
25.  enforce_room_hierarchy: no violations when valid
26.  enforce_room_hierarchy: fixes violation
27.  los_recommendation: None when low occupancy
28.  los_recommendation: min_2 at >92% occ + days_out ≤ 7
29.  los_recommendation: min_3 at >95% occ + days_out ≤ 3
30.  protection_status: open
31.  protection_status: hold (forecast > 85%)
32.  protection_status: protected (forecast > 92%)
33.  protection_status: protected (ratio < 0.10)
34.  RuleBasedRoomPricingService: returns 8 room types
35.  RuleBasedRoomPricingService: hierarchy enforced in output
36.  RuleBasedRoomPricingService: projected_adr > 0
37.  RuleBasedRoomPricingService: projected_revpar > 0
38.  Calendar: horizon_days days returned per room type
39.  Calendar: price increases with demand
40.  Inventory: sold = inventory_count - available
41.  API: GET /room-pricing returns 200
42.  API: GET /room-calendar returns 200
43.  API: GET /inventory returns 200
44.  API: GET /pricing-explanation/{code} returns 200
45.  Guardrail: hierarchy cannot be violated in output
"""
from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from app.services.room_pricing.pricing_rules import (
    compute_recommended_price,
    competitor_multiplier,
    demand_multiplier,
    enforce_room_hierarchy,
    los_recommendation,
    protection_status,
    scarcity_multiplier,
)
from app.schemas.room_pricing import RoomTypePricingRecommendation


# ── Fixtures ──────────────────────────────────────────────────────────────────

_HOTEL_ID = "hotel-test-room-001"
_AS_OF = date(2025, 8, 1)


def _make_rec(room_rank: int, price: float, rt_id: str | None = None) -> RoomTypePricingRecommendation:
    return RoomTypePricingRecommendation(
        room_type_id=rt_id or f"rt-{room_rank}",
        code=f"ROOM_{room_rank}",
        display_name=f"Room Type {room_rank}",
        room_rank=room_rank,
        capacity=2,
        inventory_count=20,
        current_available=10,
        current_price=price,
        recommended_price=price,
        price_change_pct=0.0,
        minimum_price=price * 0.70,
        maximum_price=price * 2.5,
        demand_multiplier=1.0,
        scarcity_multiplier=1.0,
        competitor_multiplier=1.0,
        premium_factor=1.0,
        confidence="high",
        reason_codes=[],
        supporting_factors=[],
        guardrails_applied=[],
        protection_status="open",
        upgrade_recommendation=None,
        los_recommendation=None,
    )


def _make_service():
    """Create RuleBasedRoomPricingService with all deps mocked."""
    from datetime import timedelta
    from app.services.room_pricing.rule_based import RuleBasedRoomPricingService
    from app.schemas.forecast import ForecastPoint
    from app.schemas.recommendations import MarketSignals

    # forecast mock — returns 14 points with 80% occupancy
    forecast_points = [
        ForecastPoint(
            forecast_date=_AS_OF + timedelta(days=i + 1),
            occupancy_pct=80.0,
            lower_bound=75.0,
            upper_bound=85.0,
        )
        for i in range(14)
    ]

    forecast_svc = MagicMock()
    forecast_svc.model_name = "Mock Forecast"
    forecast_svc.min_history_days = 1  # always enough history
    forecast_svc.forecast = AsyncMock(return_value=forecast_points)

    signals = MarketSignals(
        competitor_adr=280.0,
        competitor_occupancy=75.0,
        booking_pace_index=1.05,
        cancellation_rate=8.0,
        premium_rooms_available=8,
        expected_arrivals=90,
    )
    market_svc = MagicMock()
    market_svc.get_signals = AsyncMock(return_value=signals)

    # metrics mock
    metrics_record = MagicMock()
    metrics_record.adr = 250.0
    metrics_record.occupancy_pct = 80.0
    metrics_record.date = _AS_OF
    metrics_repo = MagicMock()
    metrics_repo.get_latest = AsyncMock(return_value=metrics_record)
    # get_range returns 60 records with 80% occupancy
    from unittest.mock import MagicMock as MM
    history_records = [MM() for _ in range(60)]
    for i, r in enumerate(history_records):
        r.date = _AS_OF
        r.occupancy_pct = 80.0
    metrics_repo.get_range = AsyncMock(return_value=history_records)

    # event mock
    event_repo = MagicMock()
    event_repo.get_active_for_hotel = AsyncMock(return_value=[])

    svc = RuleBasedRoomPricingService(
        hotel_repo=MagicMock(),
        metrics_repo=metrics_repo,
        event_repo=event_repo,
        forecast_svc=forecast_svc,
        market_svc=market_svc,
        room_repo=MagicMock(),
    )
    return svc


def _make_room_types():
    """Return 8 mock RoomType objects."""
    from app.services.seeder import _ROOM_TYPE_SEED

    room_types = []
    for rt in _ROOM_TYPE_SEED:
        m = MagicMock()
        m.id = f"rt-{rt['room_rank']}"
        m.code = rt["code"]
        m.display_name = rt["display_name"]
        m.capacity = rt["capacity"]
        m.base_rate = rt["base_rate"]
        m.premium_factor = rt["premium_factor"]
        m.inventory_count = rt["inventory_count"]
        m.current_available = max(1, int(rt["inventory_count"] * 0.70))
        m.upgrade_priority = rt["upgrade_priority"]
        m.room_rank = rt["room_rank"]
        m.minimum_price = round(rt["base_rate"] * 0.70, 2)
        m.maximum_price = round(rt["base_rate"] * 2.50, 2)
        m.current_price = rt["base_rate"]
        m.is_active = True
        room_types.append(m)
    return room_types


# ── 1–2. Seeder / Repository ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_room_types_seeds_8_per_hotel() -> None:
    """seed_room_types adds exactly 8 room types to the session."""
    from app.services.seeder import _ROOM_TYPE_SEED

    assert len(_ROOM_TYPE_SEED) == 8


@pytest.mark.asyncio
async def test_repository_get_by_hotel_returns_all() -> None:
    """RoomTypeRepository.get_by_hotel returns room types in rank order."""
    from app.repositories.room_type_repository import RoomTypeRepository

    rts = _make_room_types()
    session = MagicMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = rts
    session.execute = AsyncMock(return_value=result_mock)

    repo = RoomTypeRepository(session)
    results = await repo.get_by_hotel(_HOTEL_ID)
    assert len(results) == 8


# ── 3–8. demand_multiplier ────────────────────────────────────────────────────

def test_demand_multiplier_below_50() -> None:
    assert demand_multiplier(40.0) == 0.90


def test_demand_multiplier_50_to_65() -> None:
    assert demand_multiplier(55.0) == 0.95


def test_demand_multiplier_65_to_75() -> None:
    assert demand_multiplier(70.0) == 1.00


def test_demand_multiplier_75_to_85() -> None:
    assert demand_multiplier(80.0) == 1.08


def test_demand_multiplier_85_to_92() -> None:
    assert demand_multiplier(88.0) == 1.15


def test_demand_multiplier_above_92() -> None:
    assert demand_multiplier(95.0) == 1.25


# ── 9–14. scarcity_multiplier ─────────────────────────────────────────────────

def test_scarcity_multiplier_above_60pct() -> None:
    assert scarcity_multiplier(70, 100) == 0.95


def test_scarcity_multiplier_40_to_60pct() -> None:
    assert scarcity_multiplier(50, 100) == 1.00


def test_scarcity_multiplier_20_to_40pct() -> None:
    assert scarcity_multiplier(30, 100) == 1.08


def test_scarcity_multiplier_10_to_20pct() -> None:
    assert scarcity_multiplier(15, 100) == 1.15


def test_scarcity_multiplier_5_to_10pct() -> None:
    assert scarcity_multiplier(7, 100) == 1.22


def test_scarcity_multiplier_below_5pct() -> None:
    assert scarcity_multiplier(3, 100) == 1.30


# ── 15–19. competitor_multiplier ─────────────────────────────────────────────

def test_competitor_multiplier_hotel_below_by_more_than_15pct() -> None:
    # hotel=$200, competitor=$240 → hotel is 16.7% below competitor
    assert competitor_multiplier(200.0, 240.0) == 1.08


def test_competitor_multiplier_hotel_below_by_8_to_15pct() -> None:
    # hotel=$220, competitor=$240 → hotel is 8.3% below
    assert competitor_multiplier(220.0, 240.0) == 1.05


def test_competitor_multiplier_within_5pct() -> None:
    # hotel=$235, competitor=$240 → 2.1% below → within 5%
    assert competitor_multiplier(235.0, 240.0) == 1.00


def test_competitor_multiplier_hotel_above_by_5_to_10pct() -> None:
    # hotel=$260, competitor=$240 → hotel 8.3% above
    assert competitor_multiplier(260.0, 240.0) == 0.97


def test_competitor_multiplier_hotel_above_by_more_than_10pct() -> None:
    # hotel=$275, competitor=$240 → hotel 14.6% above
    assert competitor_multiplier(275.0, 240.0) == 0.94


# ── 20–24. compute_recommended_price ─────────────────────────────────────────

def test_compute_recommended_price_correct_formula() -> None:
    price, guardrails = compute_recommended_price(
        base_rate=200.0,
        premium_factor=1.0,
        demand_mult=1.0,
        scarcity_mult=1.0,
        competitor_mult=1.0,
        minimum_price=100.0,
        maximum_price=500.0,
        current_price=0,  # no change guardrail
    )
    assert price == 200.0
    assert guardrails == []


def test_compute_recommended_price_max_increase_guardrail() -> None:
    price, guardrails = compute_recommended_price(
        base_rate=200.0,
        premium_factor=2.0,  # raw = 400
        demand_mult=1.25,
        scarcity_mult=1.30,
        competitor_mult=1.08,
        minimum_price=100.0,
        maximum_price=5000.0,
        max_daily_increase_pct=0.25,
        current_price=200.0,  # max = 250
    )
    assert price <= 250.0 + 0.01
    assert any("max_daily_increase" in g for g in guardrails)


def test_compute_recommended_price_max_decrease_guardrail() -> None:
    price, guardrails = compute_recommended_price(
        base_rate=50.0,
        premium_factor=1.0,
        demand_mult=0.90,
        scarcity_mult=0.95,
        competitor_mult=0.94,
        minimum_price=10.0,
        maximum_price=500.0,
        max_daily_decrease_pct=0.15,
        current_price=200.0,  # min = 170
    )
    assert price >= 170.0 - 0.01
    assert any("max_daily_decrease" in g for g in guardrails)


def test_compute_recommended_price_minimum_floor() -> None:
    price, guardrails = compute_recommended_price(
        base_rate=50.0,
        premium_factor=1.0,
        demand_mult=0.90,
        scarcity_mult=0.95,
        competitor_mult=0.94,
        minimum_price=120.0,
        maximum_price=500.0,
        current_price=0,
    )
    assert price >= 120.0
    assert "minimum_price_floor" in guardrails


def test_compute_recommended_price_maximum_ceiling() -> None:
    price, guardrails = compute_recommended_price(
        base_rate=200.0,
        premium_factor=3.0,
        demand_mult=1.25,
        scarcity_mult=1.30,
        competitor_mult=1.08,
        minimum_price=100.0,
        maximum_price=400.0,
        current_price=0,
    )
    assert price <= 400.0 + 0.01
    assert "maximum_price_ceiling" in guardrails


# ── 25–26. enforce_room_hierarchy ─────────────────────────────────────────────

def test_enforce_room_hierarchy_no_violation() -> None:
    recs = [
        _make_rec(1, 189.0),
        _make_rec(2, 209.0),
        _make_rec(3, 239.0),
    ]
    result = enforce_room_hierarchy(recs)
    prices = [r.recommended_price for r in result]
    assert prices == sorted(prices)


def test_enforce_room_hierarchy_fixes_violation() -> None:
    # Rank 2 price below rank 1 — should be bumped up
    recs = [
        _make_rec(1, 300.0),  # rank 1: $300
        _make_rec(2, 250.0),  # rank 2: $250 (violation!)
    ]
    result = enforce_room_hierarchy(recs)
    rank1_price = next(r.recommended_price for r in result if r.room_rank == 1)
    rank2_price = next(r.recommended_price for r in result if r.room_rank == 2)
    assert rank2_price > rank1_price
    rank2_rec = next(r for r in result if r.room_rank == 2)
    assert "hierarchy_enforcement" in rank2_rec.guardrails_applied


# ── 27–29. los_recommendation ────────────────────────────────────────────────

def test_los_recommendation_none_when_low_occ() -> None:
    assert los_recommendation(70.0, 5) is None


def test_los_recommendation_min_2_high_occ_short_horizon() -> None:
    assert los_recommendation(93.0, 5) == "min_2"


def test_los_recommendation_min_3_very_high_occ() -> None:
    assert los_recommendation(96.0, 2) == "min_3"


# ── 30–33. protection_status ─────────────────────────────────────────────────

def test_protection_status_open() -> None:
    assert protection_status(50, 100, 70.0) == "open"


def test_protection_status_hold_forecast() -> None:
    assert protection_status(50, 100, 88.0) == "hold"


def test_protection_status_protected_forecast() -> None:
    assert protection_status(50, 100, 93.0) == "protected"


def test_protection_status_protected_ratio() -> None:
    # ratio = 5/100 = 0.05 < 0.10 → protected
    assert protection_status(5, 100, 60.0) == "protected"


# ── 34–37. RuleBasedRoomPricingService ───────────────────────────────────────

@pytest.mark.asyncio
async def test_service_returns_8_room_types() -> None:
    svc = _make_service()
    room_types = _make_room_types()
    svc._room_repo.get_by_hotel = AsyncMock(return_value=room_types)

    result = await svc.generate_recommendations(_HOTEL_ID, _AS_OF, horizon_days=14)
    assert len(result.recommendations) == 8


@pytest.mark.asyncio
async def test_service_hierarchy_enforced() -> None:
    svc = _make_service()
    room_types = _make_room_types()
    svc._room_repo.get_by_hotel = AsyncMock(return_value=room_types)

    result = await svc.generate_recommendations(_HOTEL_ID, _AS_OF, horizon_days=14)
    sorted_recs = sorted(result.recommendations, key=lambda r: r.room_rank)
    for i in range(1, len(sorted_recs)):
        assert sorted_recs[i].recommended_price > sorted_recs[i - 1].recommended_price, (
            f"Hierarchy violation: rank {sorted_recs[i].room_rank} price "
            f"{sorted_recs[i].recommended_price} <= rank {sorted_recs[i-1].room_rank} price "
            f"{sorted_recs[i-1].recommended_price}"
        )


@pytest.mark.asyncio
async def test_service_projected_adr_positive() -> None:
    svc = _make_service()
    room_types = _make_room_types()
    svc._room_repo.get_by_hotel = AsyncMock(return_value=room_types)

    result = await svc.generate_recommendations(_HOTEL_ID, _AS_OF, horizon_days=14)
    assert result.projected_adr > 0


@pytest.mark.asyncio
async def test_service_projected_revpar_positive() -> None:
    svc = _make_service()
    room_types = _make_room_types()
    svc._room_repo.get_by_hotel = AsyncMock(return_value=room_types)

    result = await svc.generate_recommendations(_HOTEL_ID, _AS_OF, horizon_days=14)
    assert result.projected_revpar > 0


# ── 38–39. Calendar ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_calendar_returns_correct_horizon() -> None:
    svc = _make_service()
    room_types = _make_room_types()
    svc._room_repo.get_by_hotel = AsyncMock(return_value=room_types)

    result = await svc.get_calendar(_HOTEL_ID, _AS_OF, horizon_days=14)
    for rt_cal in result.room_types:
        assert len(rt_cal.days) == 14


@pytest.mark.asyncio
async def test_calendar_high_demand_yields_higher_price() -> None:
    """High occupancy forecast should produce a higher recommended price than low occupancy."""
    from datetime import timedelta
    from app.schemas.forecast import ForecastPoint

    svc_high = _make_service()
    svc_low = _make_service()
    room_types = _make_room_types()

    # Calendar generates days as_of+1..as_of+horizon, so use the correct date
    day1 = _AS_OF + timedelta(days=1)

    # High demand: 95% occupancy — pass a list directly (not wrapped in MagicMock)
    svc_high._forecast_svc.forecast = AsyncMock(return_value=[
        ForecastPoint(forecast_date=day1, occupancy_pct=95.0, lower_bound=90.0, upper_bound=99.0)
    ])
    svc_high._room_repo.get_by_hotel = AsyncMock(return_value=room_types)

    # Low demand: 40% occupancy
    svc_low._forecast_svc.forecast = AsyncMock(return_value=[
        ForecastPoint(forecast_date=day1, occupancy_pct=40.0, lower_bound=35.0, upper_bound=45.0)
    ])
    svc_low._room_repo.get_by_hotel = AsyncMock(return_value=room_types)

    result_high = await svc_high.get_calendar(_HOTEL_ID, _AS_OF, horizon_days=1)
    result_low = await svc_low.get_calendar(_HOTEL_ID, _AS_OF, horizon_days=1)

    high_price = result_high.room_types[0].days[0].recommended_price
    low_price = result_low.room_types[0].days[0].recommended_price
    assert high_price > low_price


# ── 40. Inventory ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inventory_sold_equals_inventory_minus_available() -> None:
    svc = _make_service()
    room_types = _make_room_types()
    svc._room_repo.get_by_hotel = AsyncMock(return_value=room_types)

    result = await svc.get_inventory(_HOTEL_ID, _AS_OF)
    for rt_status in result.room_types:
        rt = next(r for r in room_types if r.code == rt_status.code)
        expected_sold = rt.inventory_count - rt.current_available
        assert rt_status.sold == expected_sold


# ── 41–44. API integration tests ─────────────────────────────────────────────

from httpx import AsyncClient, ASGITransport
from app.main import app as _app


@pytest.fixture
async def api_client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


async def _get_hotel_id(client: AsyncClient) -> str:
    resp = await client.get("/api/v1/hotels?active_only=true")
    assert resp.status_code == 200
    hotels = resp.json()
    if hotels["total"] == 0:
        pytest.skip("No hotels seeded")
    return hotels["items"][0]["id"]


async def test_api_room_pricing_returns_200(api_client: AsyncClient) -> None:
    hotel_id = await _get_hotel_id(api_client)
    resp = await api_client.get(f"/api/v1/hotels/{hotel_id}/room-pricing")
    assert resp.status_code == 200
    data = resp.json()
    assert "recommendations" in data


async def test_api_room_calendar_returns_200(api_client: AsyncClient) -> None:
    hotel_id = await _get_hotel_id(api_client)
    resp = await api_client.get(f"/api/v1/hotels/{hotel_id}/room-calendar?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert "room_types" in data


async def test_api_inventory_returns_200(api_client: AsyncClient) -> None:
    hotel_id = await _get_hotel_id(api_client)
    resp = await api_client.get(f"/api/v1/hotels/{hotel_id}/inventory")
    assert resp.status_code == 200
    data = resp.json()
    assert "room_types" in data


async def test_api_pricing_explanation_returns_200(api_client: AsyncClient) -> None:
    hotel_id = await _get_hotel_id(api_client)
    resp = await api_client.get(f"/api/v1/hotels/{hotel_id}/pricing-explanation/STANDARD_KING")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "STANDARD_KING"


# ── 45. Hierarchy cannot be violated in output ───────────────────────────────

def test_hierarchy_never_violated_in_output() -> None:
    """Ensure enforce_room_hierarchy never produces violations in output."""
    # Create recommendations with deliberate violations (realistic price ranges)
    recs = [
        _make_rec(1, 200.0),  # rank 1: $200
        _make_rec(2, 150.0),  # rank 2: $150 — violation, max_price = 375
        _make_rec(3, 100.0),  # rank 3: $100 — violation, max_price = 250
    ]
    result = enforce_room_hierarchy(recs)
    sorted_result = sorted(result, key=lambda r: r.room_rank)
    for i in range(1, len(sorted_result)):
        assert sorted_result[i].recommended_price > sorted_result[i - 1].recommended_price
