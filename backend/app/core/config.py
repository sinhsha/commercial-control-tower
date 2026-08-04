from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    app_name: str = "Hotel Control Tower"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./hotel_control_tower.db"

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton – use as a FastAPI dependency."""
    return Settings()
