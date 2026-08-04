from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# Anchor all relative paths to the backend/ directory regardless of CWD.
# The DB lives one level up at the project root (hotel-control-tower/) because
# uvicorn runs with --app-dir backend but CWD is the project root.
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_ENV_FILE = _BACKEND_DIR / ".env"
_DEFAULT_DB_URL = f"sqlite+aiosqlite:///{_PROJECT_ROOT / 'hotel_control_tower.db'}"


class Settings(BaseSettings):
    # Application
    app_name: str = "Hotel Control Tower"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database — absolute path so it resolves correctly regardless of CWD
    database_url: str = _DEFAULT_DB_URL

    # CORS – comma-separated list of allowed origins
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    # Future: AI / ML service URLs (pluggable extension points)
    forecasting_service_url: str | None = None
    optimization_service_url: str | None = None
    explanation_service_url: str | None = None

    # Future: External rate-shopping / demand-data feeds
    rate_shop_api_key: str | None = None

    # LLM / Copilot
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    copilot_enabled: bool = True
    copilot_max_tokens: int = 600

    # Enterprise Forecasting Platform
    forecast_provider: str = "baseline"          # baseline | timesfm | auto
    timesfm_enabled: bool = True
    timesfm_timeout_seconds: float = 60.0
    timesfm_model_name: str = "google/timesfm-2.5-200m-pytorch"
    timesfm_context_length: int = 512
    timesfm_device: str = "cpu"
    forecast_evaluation_window: str = "last_30"
    forecast_governance_max_jump_pp: float = 30.0
    forecast_governance_min_history_days: int = 14
    forecast_auto_selector_ttl_seconds: int = 3600

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8"}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton – use as a FastAPI dependency."""
    return Settings()


def _bust_settings_cache() -> None:
    """Clear the lru_cache so the next call re-reads the .env file.
    Called automatically on uvicorn reload via app startup."""
    get_settings.cache_clear()
