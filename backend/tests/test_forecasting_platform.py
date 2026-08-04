"""
Tests for the Enterprise Forecasting Platform.

35 tests covering:
  - Model registry (1-3)
  - TimesFMForecastService fallback (4-5)
  - Evaluation metrics (6-15)
  - Governance rules (16-24)
  - AutoModelSelector (25-26)
  - ForecastManagerService (27-30)
  - API endpoints (31-35) — uses httpx AsyncClient
"""
from __future__ import annotations

import math
import pytest
from datetime import date, datetime, timedelta, timezone

from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.forecast import ForecastPoint
from app.schemas.forecasting import EvaluationResult
from app.services.forecasting.model_registry import (
    ForecastModelRegistry,
    ModelEntry,
)
from app.services.forecasting.evaluation import (
    ForecastEvaluationService,
    _mae, _rmse, _mape, _wape, _bias, _coverage,
)
from app.services.forecasting.governance import ForecastGovernanceService
from app.services.forecasting.auto_selector import AutoModelSelector, select_best
from app.services.forecasting.seasonal_baseline import SeasonalBaselineForecastService
from app.services.forecasting.timesfm_service import TimesFMForecastService
from app.services.forecasting.manager import ForecastManagerService
from app.services.forecasting.comparison import ForecastComparisonService


# ── Shared async client fixture ───────────────────────────────────────────────

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── Shared fixtures ──────────────────────────────────────────────────────────

def _make_history(days: int = 90, base: float = 70.0) -> list[tuple[date, float]]:
    start = date(2024, 1, 1)
    return [(start + timedelta(days=i), base + (5.0 if (start + timedelta(days=i)).weekday() >= 5 else 0.0))
            for i in range(days)]


def _make_forecast_points(
    origin: date,
    horizon: int = 14,
    base_occ: float = 70.0,
) -> list[ForecastPoint]:
    return [
        ForecastPoint(
            forecast_date=origin + timedelta(days=h),
            occupancy_pct=base_occ,
            lower_bound=max(0.0, base_occ - 5.0),
            upper_bound=min(100.0, base_occ + 5.0),
        )
        for h in range(1, horizon + 1)
    ]


def _dummy_eval(model_id: str, wape: float, bias: float, runtime_ms: float) -> EvaluationResult:
    return EvaluationResult(
        model_id=model_id,
        model_name=model_id,
        window="last_30",
        mae=1.0, rmse=1.5, mape=2.0,
        wape=wape, bias=bias, mean_error=bias,
        coverage=80.0, runtime_ms=runtime_ms,
        evaluated_at=datetime.now(timezone.utc),
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1-3: Model Registry
# ══════════════════════════════════════════════════════════════════════════════

class TestModelRegistry:

    def test_register_and_lookup(self) -> None:
        """Test 1 — register a model then retrieve by id."""
        registry = ForecastModelRegistry()
        entry = ModelEntry(
            model_id="test_model",
            name="Test Model",
            version="2.0.0",
            provider="acme",
            device="cpu",
            supported_horizons=[1, 7, 14],
            capabilities=["occupancy_forecast"],
            status="active",
        )
        registry.register(entry)
        result = registry.get("test_model")
        assert result is not None
        assert result.model_id == "test_model"
        assert result.name == "Test Model"

    def test_list_all(self) -> None:
        """Test 2 — list_all returns all registered models."""
        registry = ForecastModelRegistry()
        for i in range(3):
            registry.register(ModelEntry(
                model_id=f"model_{i}",
                name=f"Model {i}",
                version="1.0.0",
                provider="test",
                device="cpu",
                supported_horizons=[14],
                capabilities=[],
                status="active",
            ))
        all_models = registry.list_all()
        assert len(all_models) == 3
        assert {m.model_id for m in all_models} == {"model_0", "model_1", "model_2"}

    def test_lookup_missing_returns_none(self) -> None:
        """Test 3 — get() on unknown id returns None."""
        registry = ForecastModelRegistry()
        assert registry.get("does_not_exist") is None


# ══════════════════════════════════════════════════════════════════════════════
# 4-5: TimesFMForecastService fallback
# ══════════════════════════════════════════════════════════════════════════════

class TestTimesFMFallback:

    @pytest.mark.anyio
    async def test_falls_back_when_not_installed(self) -> None:
        """Test 4 — TimesFM not installed → fallback to SeasonalBaseline."""
        svc = TimesFMForecastService()
        # timesfm is not installed in test env, so _available should be False
        history = _make_history(90)
        origin = history[-1][0]

        result = await svc.forecast("h1", history, horizon=14, origin=origin)

        assert svc.is_fallback is True
        assert "not installed" in (svc.fallback_reason or "")
        assert len(result) == 14

    @pytest.mark.anyio
    async def test_fallback_result_same_shape_as_baseline(self) -> None:
        """Test 5 — fallback result has the same shape as SeasonalBaseline output."""
        timesfm_svc = TimesFMForecastService()
        baseline_svc = SeasonalBaselineForecastService()

        history = _make_history(90)
        origin = history[-1][0]
        horizon = 14

        timesfm_result = await timesfm_svc.forecast("h1", history, horizon=horizon, origin=origin)
        baseline_result = await baseline_svc.forecast("h1", history, horizon=horizon, origin=origin)

        assert len(timesfm_result) == len(baseline_result)
        for tp, bp in zip(timesfm_result, baseline_result):
            assert hasattr(tp, "forecast_date")
            assert hasattr(tp, "occupancy_pct")
            assert hasattr(tp, "lower_bound")
            assert hasattr(tp, "upper_bound")


# ══════════════════════════════════════════════════════════════════════════════
# 6-15: Evaluation metrics
# ══════════════════════════════════════════════════════════════════════════════

class TestEvaluationMetrics:

    def test_mae_correct(self) -> None:
        """Test 6 — MAE computed correctly on known inputs."""
        actuals = [80.0, 70.0, 60.0]
        predicted = [78.0, 72.0, 63.0]
        expected = (2.0 + 2.0 + 3.0) / 3
        assert _mae(actuals, predicted) == pytest.approx(expected, abs=1e-9)

    def test_rmse_correct(self) -> None:
        """Test 7 — RMSE computed correctly."""
        actuals = [80.0, 70.0]
        predicted = [76.0, 74.0]  # errors: -4, +4
        expected = math.sqrt((16 + 16) / 2)
        assert _rmse(actuals, predicted) == pytest.approx(expected, abs=1e-9)

    def test_mape_correct(self) -> None:
        """Test 8 — MAPE computed correctly (no zero actuals)."""
        actuals = [100.0, 50.0]
        predicted = [110.0, 55.0]  # 10%, 10%
        assert _mape(actuals, predicted) == pytest.approx(10.0, abs=1e-6)

    def test_wape_correct(self) -> None:
        """Test 9 — WAPE computed correctly."""
        actuals = [100.0, 100.0]
        predicted = [110.0, 90.0]  # absolute errors: 10, 10 → sum=20, sum|actual|=200
        assert _wape(actuals, predicted) == pytest.approx(10.0, abs=1e-6)

    def test_bias_correct(self) -> None:
        """Test 10 — Bias (mean of predicted – actual) computed correctly."""
        actuals = [80.0, 70.0, 60.0]
        predicted = [85.0, 75.0, 65.0]  # all +5
        assert _bias(actuals, predicted) == pytest.approx(5.0, abs=1e-9)

    def test_coverage_all_inside(self) -> None:
        """Test 11 — Coverage = 100% when all actuals within CI."""
        actuals = [70.0, 75.0, 65.0]
        lowers = [65.0, 70.0, 60.0]
        uppers = [75.0, 80.0, 70.0]
        assert _coverage(actuals, lowers, uppers) == pytest.approx(100.0)

    def test_coverage_none_inside(self) -> None:
        """Test 12 — Coverage = 0% when no actuals within CI."""
        actuals = [50.0, 50.0]
        lowers = [60.0, 60.0]
        uppers = [70.0, 70.0]
        assert _coverage(actuals, lowers, uppers) == pytest.approx(0.0)

    def test_coverage_partial(self) -> None:
        """Test 13 — Coverage = 50% when half of actuals within CI."""
        actuals = [70.0, 50.0]
        lowers = [65.0, 60.0]
        uppers = [75.0, 70.0]
        assert _coverage(actuals, lowers, uppers) == pytest.approx(50.0)

    def test_coverage_correct_partial_coverage(self) -> None:
        """Test 14 — Validate % of actuals within confidence bounds."""
        actuals = [68.0, 72.0, 65.0, 80.0]
        lowers = [65.0, 70.0, 60.0, 85.0]  # last one: actual 80 < lower 85 → miss
        uppers = [75.0, 75.0, 70.0, 95.0]
        result = _coverage(actuals, lowers, uppers)
        assert result == pytest.approx(75.0)

    @pytest.mark.anyio
    async def test_evaluation_handles_empty_history(self) -> None:
        """Test 15 — Evaluation returns zero metrics on empty / short history."""
        svc = ForecastEvaluationService(SeasonalBaselineForecastService())
        result = await svc.evaluate(
            hotel_id="h1",
            history=[],  # empty
            window="last_30",
            model_id="seasonal_baseline",
        )
        assert result.mae == 0.0
        assert result.rmse == 0.0
        assert result.wape == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# 16-24: Governance
# ══════════════════════════════════════════════════════════════════════════════

class TestGovernance:

    @pytest.mark.anyio
    async def test_passes_valid_forecast(self) -> None:
        """Test 16 — governance passes a clean forecast."""
        gov = ForecastGovernanceService(max_jump_pp=30.0, min_history_days=14)
        history = _make_history(30)
        origin = history[-1][0]
        points = _make_forecast_points(origin, horizon=14, base_occ=70.0)

        final, result = await gov.validate_and_govern(
            hotel_id="h1",
            forecast_points=points,
            history=history,
            origin=origin,
            horizon=14,
        )
        assert result.validation_status in ("passed", "warning")
        assert result.fallback_used is False

    @pytest.mark.anyio
    async def test_fails_occupancy_above_100(self) -> None:
        """Test 17 — governance: ForecastPoint rejects occupancy > 100 at schema level."""
        import pydantic
        # The ForecastPoint schema itself enforces [0, 100].
        # Verify this enforcement is in place so governance never sees invalid values.
        with pytest.raises(pydantic.ValidationError):
            ForecastPoint(
                forecast_date=date.today(),
                occupancy_pct=110.0,
                lower_bound=100.0,
                upper_bound=100.0,
            )

    @pytest.mark.anyio
    async def test_fails_occupancy_below_zero(self) -> None:
        """Test 18 — governance: ForecastPoint rejects occupancy < 0 at schema level."""
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            ForecastPoint(
                forecast_date=date.today(),
                occupancy_pct=-5.0,
                lower_bound=-10.0,
                upper_bound=10.0,
            )

    @pytest.mark.anyio
    async def test_fails_missing_date_in_sequence(self) -> None:
        """Test 19 — governance fails on missing date."""
        gov = ForecastGovernanceService(max_jump_pp=30.0, min_history_days=14)
        history = _make_history(30)
        origin = history[-1][0]
        # Create 14-day points but remove day 5
        points = _make_forecast_points(origin, horizon=14)
        points_with_gap = [p for p in points if p.forecast_date != origin + timedelta(days=5)]

        final, result = await gov.validate_and_govern(
            hotel_id="h1",
            forecast_points=points_with_gap,
            history=history,
            origin=origin,
            horizon=14,
        )
        assert result.fallback_used is True
        assert any("Missing" in w for w in result.warnings)

    @pytest.mark.anyio
    async def test_fails_duplicate_date(self) -> None:
        """Test 20 — governance fails on duplicate forecast date."""
        gov = ForecastGovernanceService(max_jump_pp=30.0, min_history_days=14)
        history = _make_history(30)
        origin = history[-1][0]
        # Add a duplicate
        points = _make_forecast_points(origin, horizon=7)
        dup = ForecastPoint(
            forecast_date=points[0].forecast_date,  # duplicate
            occupancy_pct=70.0,
            lower_bound=65.0,
            upper_bound=75.0,
        )
        duplicate_points = [dup] + points  # duplicate at start

        final, result = await gov.validate_and_govern(
            hotel_id="h1",
            forecast_points=duplicate_points,
            history=history,
            origin=origin,
            horizon=7,
        )
        assert result.fallback_used is True
        assert any("Duplicate" in w for w in result.warnings)

    @pytest.mark.anyio
    async def test_flags_large_day_over_day_jump(self) -> None:
        """Test 21 — governance flags day-over-day jump > threshold as warning."""
        gov = ForecastGovernanceService(max_jump_pp=5.0, min_history_days=14)
        history = _make_history(30, base=50.0)
        origin = history[-1][0]
        # Last historical value is 50pp. First forecast day jumps to 90pp (+40pp > threshold 5pp)
        points = [
            ForecastPoint(
                forecast_date=origin + timedelta(days=h),
                occupancy_pct=90.0 if h == 1 else 50.0,
                lower_bound=80.0 if h == 1 else 45.0,
                upper_bound=95.0 if h == 1 else 55.0,
            )
            for h in range(1, 8)
        ]

        final, result = await gov.validate_and_govern(
            hotel_id="h1",
            forecast_points=points,
            history=history,
            origin=origin,
            horizon=7,
        )
        # Should be warning (not failed) because jump > max_jump_pp
        assert result.validation_status in ("warning", "failed")
        assert len(result.warnings) > 0

    @pytest.mark.anyio
    async def test_fails_invalid_confidence_interval(self) -> None:
        """Test 22 — governance fails when lower_bound > occupancy_pct."""
        gov = ForecastGovernanceService(max_jump_pp=30.0, min_history_days=14)
        history = _make_history(30)
        origin = history[-1][0]

        # We need to create a ForecastPoint where lower_bound > occupancy_pct.
        # Pydantic validates [0,100] but doesn't enforce lower <= value.
        bad_point = ForecastPoint(
            forecast_date=origin + timedelta(days=1),
            occupancy_pct=60.0,
            lower_bound=70.0,   # violation: lower > value
            upper_bound=80.0,
        )
        rest = _make_forecast_points(origin, horizon=14)[1:]  # days 2-14
        all_points = [bad_point] + rest

        final, result = await gov.validate_and_govern(
            hotel_id="h1",
            forecast_points=all_points,
            history=history,
            origin=origin,
            horizon=14,
        )
        assert result.fallback_used is True
        assert any("lower_bound" in w for w in result.warnings)

    @pytest.mark.anyio
    async def test_fallback_to_baseline_on_failure(self) -> None:
        """Test 23 — on governance failure, output is a valid baseline forecast."""
        fallback = SeasonalBaselineForecastService()
        gov = ForecastGovernanceService(
            fallback_svc=fallback,
            max_jump_pp=30.0,
            min_history_days=14,
        )
        history = _make_history(30)
        origin = history[-1][0]
        # Force failure by passing empty points
        final, result = await gov.validate_and_govern(
            hotel_id="h1",
            forecast_points=[],
            history=history,
            origin=origin,
            horizon=14,
        )
        assert result.fallback_used is True
        assert len(final) == 14
        for fp in final:
            assert 0.0 <= fp.occupancy_pct <= 100.0

    @pytest.mark.anyio
    async def test_insufficient_history_triggers_fallback(self) -> None:
        """Test 24 — insufficient history triggers governance fallback (empty forecast)."""
        gov = ForecastGovernanceService(max_jump_pp=30.0, min_history_days=14)
        short_history = _make_history(5)  # less than min_history_days=14
        origin = short_history[-1][0]
        points = _make_forecast_points(origin, horizon=7)

        final, result = await gov.validate_and_govern(
            hotel_id="h1",
            forecast_points=points,
            history=short_history,
            origin=origin,
            horizon=7,
        )
        assert result.fallback_used is True
        assert result.validation_status == "failed"
        # Fallback also fails since short history can't run baseline → returns []
        assert isinstance(final, list)


# ══════════════════════════════════════════════════════════════════════════════
# 25-26: AutoModelSelector
# ══════════════════════════════════════════════════════════════════════════════

class TestAutoModelSelector:

    def test_selects_lowest_wape(self) -> None:
        """Test 25 — selects model with lowest WAPE."""
        results = [
            _dummy_eval("model_a", wape=15.0, bias=1.0, runtime_ms=100.0),
            _dummy_eval("model_b", wape=10.0, bias=2.0, runtime_ms=200.0),  # ← lowest WAPE
        ]
        model_id, reason = select_best(results)
        assert model_id == "model_b"
        assert "WAPE" in reason

    def test_tiebreaks_by_bias_then_runtime(self) -> None:
        """Test 26 — on equal WAPE, selects by |bias|, then runtime_ms."""
        results = [
            _dummy_eval("model_a", wape=10.0, bias=3.0, runtime_ms=50.0),
            _dummy_eval("model_b", wape=10.0, bias=1.0, runtime_ms=200.0),  # ← lower bias
            _dummy_eval("model_c", wape=10.0, bias=1.0, runtime_ms=100.0),  # ← same bias, faster
        ]
        model_id, _ = select_best(results)
        assert model_id == "model_c"  # lowest wape + bias + fastest runtime


# ══════════════════════════════════════════════════════════════════════════════
# 27-30: ForecastManagerService
# ══════════════════════════════════════════════════════════════════════════════

class TestForecastManagerService:

    @pytest.mark.anyio
    async def test_baseline_provider_returns_managed_result(self) -> None:
        """Test 27 — baseline provider returns a ManagedForecastResult."""
        manager = ForecastManagerService(provider="baseline")
        history = _make_history(90)
        origin = history[-1][0]

        result = await manager.forecast(
            hotel_id="h1",
            history=history,
            horizon=14,
            origin=origin,
        )
        assert result.model_used in ("seasonal_baseline", "timesfm")
        assert len(result.forecast) == 14

    @pytest.mark.anyio
    async def test_metadata_fields_present(self) -> None:
        """Test 28 — result has all required metadata fields."""
        manager = ForecastManagerService(provider="baseline")
        history = _make_history(90)
        origin = history[-1][0]

        result = await manager.forecast("h1", history, horizon=7, origin=origin)

        assert result.forecast_id is not None
        assert result.hotel_id == "h1"
        assert result.model_used is not None
        assert result.generated_at is not None
        assert isinstance(result.runtime_ms, float)
        assert isinstance(result.training_context_days, int)
        assert result.prediction_horizon == 7
        assert result.validation_status in ("passed", "warning", "failed")
        assert isinstance(result.fallback_used, bool)
        assert isinstance(result.warnings, list)

    @pytest.mark.anyio
    async def test_fallback_used_false_when_governance_passes(self) -> None:
        """Test 29 — fallback_used=False when governance passes."""
        manager = ForecastManagerService(provider="baseline")
        history = _make_history(90)
        origin = history[-1][0]

        result = await manager.forecast("h1", history, horizon=14, origin=origin)
        # With good data and baseline, governance should pass
        assert result.fallback_used is False

    @pytest.mark.anyio
    async def test_fallback_used_true_when_governance_fails(self) -> None:
        """Test 30 — fallback_used=True when governance detects failure."""
        # Use a governance service that always fails
        class AlwaysFailGovernance(ForecastGovernanceService):
            async def validate_and_govern(self, hotel_id, forecast_points, history, origin, horizon):
                final, result = await self._do_fallback(
                    hotel_id, history, origin, horizon,
                    ["Forced failure for test"], "Forced failure for test"
                )
                return final, result

        gov = AlwaysFailGovernance(max_jump_pp=30.0, min_history_days=14)
        manager = ForecastManagerService(provider="baseline", governance_svc=gov)
        history = _make_history(90)
        origin = history[-1][0]

        result = await manager.forecast("h1", history, horizon=14, origin=origin)
        assert result.fallback_used is True


# ══════════════════════════════════════════════════════════════════════════════
# 31-35: API endpoints
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_api_models_returns_200(async_client) -> None:
    """Test 31 — GET /forecast/models returns 200."""
    response = await async_client.get("/api/v1/forecast/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert data["total"] >= 2


@pytest.mark.anyio
async def test_api_health_returns_200(async_client) -> None:
    """Test 32 — GET /forecast/health returns 200."""
    # First get a valid hotel_id from the hotels endpoint
    hotels_response = await async_client.get("/api/v1/hotels?active_only=true")
    assert hotels_response.status_code == 200
    hotel_id = hotels_response.json()["items"][0]["id"]

    response = await async_client.get(f"/api/v1/forecast/health?hotel_id={hotel_id}")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("healthy", "warning", "degraded")


@pytest.mark.anyio
async def test_api_evaluation_returns_200(async_client) -> None:
    """Test 33 — GET /forecast/evaluation returns 200."""
    hotels_response = await async_client.get("/api/v1/hotels?active_only=true")
    hotel_id = hotels_response.json()["items"][0]["id"]

    response = await async_client.get(
        f"/api/v1/forecast/evaluation?hotel_id={hotel_id}&window=last_30&model=baseline"
    )
    assert response.status_code == 200
    data = response.json()
    assert "mae" in data
    assert "wape" in data


@pytest.mark.anyio
async def test_api_comparison_returns_200(async_client) -> None:
    """Test 34 — GET /forecast/comparison returns 200."""
    hotels_response = await async_client.get("/api/v1/hotels?active_only=true")
    hotel_id = hotels_response.json()["items"][0]["id"]

    response = await async_client.get(
        f"/api/v1/forecast/comparison?hotel_id={hotel_id}&days=30"
    )
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert "recommended_model_id" in data


@pytest.mark.anyio
async def test_api_backtest_returns_200(async_client) -> None:
    """Test 35 — GET /forecast/backtest returns 200."""
    hotels_response = await async_client.get("/api/v1/hotels?active_only=true")
    hotel_id = hotels_response.json()["items"][0]["id"]

    response = await async_client.get(
        f"/api/v1/forecast/backtest?hotel_id={hotel_id}&window=last_30&model=baseline"
    )
    assert response.status_code == 200
    data = response.json()
    assert "points" in data
    assert "mae" in data
