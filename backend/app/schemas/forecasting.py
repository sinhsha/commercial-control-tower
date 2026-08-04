"""
Enterprise Forecasting Platform — Pydantic schemas.

These are NEW schemas for the platform endpoints.
They do NOT replace or modify the existing ForecastPoint / ForecastResponse in
app/schemas/forecast.py — those remain untouched.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Model Registry ────────────────────────────────────────────────────────────

class ForecastModelInfo(BaseModel):
    """Metadata for a registered forecast model."""

    model_config = {"protected_namespaces": ()}

    model_id: str
    name: str
    version: str
    provider: str
    device: str
    supported_horizons: list[int]
    capabilities: list[str]
    status: Literal["active", "inactive", "degraded"]


class ForecastModelListResponse(BaseModel):
    total: int
    models: list[ForecastModelInfo]


# ── Evaluation ────────────────────────────────────────────────────────────────

class EvaluationResult(BaseModel):
    """Per-model back-evaluation metrics."""

    model_config = {"protected_namespaces": ()}

    model_id: str
    model_name: str
    window: str
    mae: float = Field(..., description="Mean Absolute Error")
    rmse: float = Field(..., description="Root Mean Squared Error")
    mape: float = Field(..., description="Mean Absolute Percentage Error")
    wape: float = Field(..., description="Weighted Absolute Percentage Error")
    bias: float = Field(..., description="Mean forecast bias (predicted – actual)")
    mean_error: float = Field(..., description="Mean signed error")
    coverage: float = Field(..., description="% of actuals within confidence interval")
    runtime_ms: float = Field(..., description="Inference wall-clock time in ms")
    evaluated_at: datetime


# ── Comparison ────────────────────────────────────────────────────────────────

class BacktestPoint(BaseModel):
    """One date's actual vs predicted values."""

    date: date
    actual: float
    predicted: float
    lower_bound: float
    upper_bound: float
    residual: float  # predicted – actual


class BacktestResult(BaseModel):
    """Backtest output: actuals vs predicted with residuals."""

    model_config = {"protected_namespaces": ()}

    model_id: str
    model_name: str
    window: str
    points: list[BacktestPoint]
    mae: float
    rmse: float
    bias: float


class ComparisonResult(BaseModel):
    """Side-by-side evaluation of all registered models."""

    hotel_id: str
    window: str
    models: list[EvaluationResult]
    recommended_model_id: str
    evaluated_at: datetime


# ── Governance ────────────────────────────────────────────────────────────────

class GovernanceResult(BaseModel):
    """Result of forecast validation checks."""

    model_config = {"protected_namespaces": ()}

    validation_status: Literal["passed", "warning", "failed"]
    warnings: list[str]
    fallback_used: bool
    fallback_reason: str | None = None


# ── Managed Forecast ──────────────────────────────────────────────────────────

class ManagedForecastResult(BaseModel):
    """Enriched forecast response returned by ForecastManagerService."""

    model_config = {"protected_namespaces": ()}

    forecast_id: str
    hotel_id: str
    model_used: str
    model_version: str
    generated_at: datetime
    runtime_ms: float
    device: str
    training_context_days: int
    prediction_horizon: int
    validation_status: Literal["passed", "warning", "failed"]
    fallback_used: bool
    fallback_reason: str | None = None
    confidence_score: float
    evaluation_metrics: EvaluationResult | None = None
    warnings: list[str]
    forecast: list[dict]  # list of ForecastPoint-like dicts for serialisation


# ── Health ────────────────────────────────────────────────────────────────────

class ForecastHealthStatus(BaseModel):
    """Traffic-light health summary for a hotel's forecast."""

    model_config = {"protected_namespaces": ()}

    hotel_id: str
    status: Literal["healthy", "warning", "degraded"]
    active_model: str
    active_model_version: str
    fallback_active: bool
    last_validation: datetime
    warnings: list[str]


# ── Audit ─────────────────────────────────────────────────────────────────────

class ForecastAuditEntry(BaseModel):
    """One entry in the forecast audit trail."""

    model_config = {"protected_namespaces": ()}

    forecast_id: str
    model: str
    metrics: EvaluationResult | None
    fallback_reason: str | None
    latency_ms: float
    timestamp: datetime
