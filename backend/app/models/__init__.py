# Re-export so `app.models` acts as a single import target for model discovery.
from app.models.hotel import Hotel  # noqa: F401
from app.models.daily_metrics import DailyMetrics  # noqa: F401
from app.models.room import Room  # noqa: F401
from app.models.demand_event import DemandEvent  # noqa: F401
