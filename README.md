# Hotel Commercial Control Tower

An AI-Powered Hotel Commercial Control Tower — a production-quality proof of concept featuring a React + TypeScript frontend, Python FastAPI backend, SQLite database, and Docker Compose orchestration.

## Architecture

```
hotel-control-tower/
├── backend/                  # Python FastAPI service
│   ├── app/
│   │   ├── api/v1/endpoints/ # Route handlers (thin controllers)
│   │   ├── core/             # Config, DI container, logging
│   │   ├── db/               # Database session & migrations
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # Business logic layer
│   │   │   ├── forecasting/      # Baseline forecast engine
│   │   │   ├── event_engine/     # Event-adjustment engine
│   │   │   ├── events/           # Event impact calculations
│   │   │   ├── market_signals/   # Market signal abstraction + mock
│   │   │   └── recommendations/  # Commercial recommendation engine ← NEW
│   │   └── repositories/     # Data access layer
│   └── tests/
├── frontend/                 # React + TypeScript app (Vite)
│   └── src/
│       ├── components/       # Dashboard, UI primitives, Charts
│       │   └── dashboard/    # RecommendationCard, RecommendationsPanel ← NEW
│       ├── hooks/            # Custom React hooks (useRecommendations ← NEW)
│       ├── services/         # API client layer
│       └── types/            # Shared TypeScript types
├── docker-compose.yml
└── README.md
```

## Quick Start

### With Docker Compose (recommended)

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### Local Development

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

---

## Features

### 1 · Historical KPI Dashboard
Real-time hotel metrics: Occupancy %, ADR, RevPAR, Available Rooms, Demand Index. Rate positioning vs compset.

### 2 · Baseline Occupancy Forecast
14-day seasonal baseline forecast using the `SeasonalBaselineForecastService`. Swappable via DI.

### 3 · Demand-Event Sensing
Active demand events (conventions, concerts, sports, festivals) visualised with distance, attendance, and confidence.

### 4 · Event-Adjusted Forecast
Confidence-weighted event uplifts layered on the baseline. Explainability panel shows per-event contributions.

### 5 · Commercial Recommendation Engine ← NEW

Rule-based engine that converts forecast + adjusted forecast + events + inventory + market signals into **prioritised commercial actions**.

#### Rules Implemented
| Rule | Trigger | Actions |
|------|---------|---------|
| **High-Demand Pricing** | Adj. occ ≥ 85% + positive uplift + competitor ADR support | Increase rate (5–12%, guardrailed) |
| **Very-High-Demand Restriction** | Adj. occ ≥ 92% + booking pace > 1× | Close discounted rates; MLOS-2 if ≥ 2 consecutive nights |
| **Low-Demand** | Adj. occ < 55% + pace below normal + no strong event | Modest rate reduction **or** breakfast package |
| **Premium Inventory** | Adj. occ > 88% + <15 premium rooms available | Protect premium inventory; restrict comps; open paid upgrades |
| **Event Package** | Convention / concert / sports / festival nearby | Parking / late checkout / event package |
| **Operational Pressure** | Adj. occ > 95% + high expected arrivals | Alert front desk, housekeeping, revenue manager |

#### Guardrails
| Guardrail | Default |
|-----------|---------|
| `maximum_rate_increase_pct` | 12% |
| `maximum_rate_decrease_pct` | 10% |
| `minimum_recommended_rate` | $79 |
| `maximum_recommended_rate` | $999 |
| `maximum_recommendations_per_hotel` | 10 |

All guardrails are configurable in `_Context` and tested.

#### Scoring Formula
```
score = revenue_component × 0.35
      + urgency_component  × 0.25
      + confidence_weight  × 0.20
      + occupancy_level    × 0.15
      + event_component    × 0.05
```
Score in [0, 100]. Priority assigned by threshold (75→critical, 55→high, 35→medium, <35→low), capped by confidence.

#### Conflict Suppression
- `increase_rate` ↔ `reduce_rate` → keep higher-scored
- `protect_premium_inventory` ↔ `release_premium_inventory`
- `close_discounted_rates` ↔ `launch_event_package`

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/hotels/{id}/recommendations` | List ranked recommendations |
| GET | `/api/v1/hotels/{id}/recommendations/{rec_id}` | Single recommendation detail |
| GET | `/api/v1/hotels/{id}/forecast/adjusted` | Event-adjusted forecast |
| GET | `/api/v1/hotels/{id}/forecast` | Baseline forecast |
| GET | `/api/v1/hotels/{id}/events` | Active demand events |
| GET | `/api/v1/metrics/dashboard/{id}` | Hotel KPI dashboard |

### Recommendations Query Parameters
```
GET /api/v1/hotels/{id}/recommendations
  ?days=14          # Forecast horizon (default 14, max 90)
  &category=pricing # Filter: pricing | inventory | restrictions | upgrade | package | ancillary | operational
  &priority=high    # Filter: critical | high | medium | low
  &status=proposed  # Filter: proposed | approved | rejected | expired
  &limit=10         # Max results (default 10)
  &as_of=2025-08-01 # Override origin date
```

### Sample Response
```json
{
  "hotel_id": "abc123",
  "generated_at": "2025-08-01T10:00:00Z",
  "forecast_model": "Seasonal Baseline",
  "adjustment_model": "Rule Based Event Engine",
  "recommendation_model": "Rule Based Commercial Engine",
  "summary": {
    "total": 4,
    "critical": 0,
    "high": 2,
    "medium": 1,
    "low": 1,
    "estimated_revenue_opportunity": 18450
  },
  "recommendations": [
    {
      "id": "REC-abc123-20250802-PRICING-001",
      "category": "pricing",
      "action": "increase_rate",
      "title": "Increase flexible rate by 8%",
      "priority": "high",
      "confidence": "high",
      "effective_start_date": "2025-08-02",
      "effective_end_date": "2025-08-04",
      "current_value": 279,
      "recommended_value": 301,
      "unit": "USD",
      "expected_revenue_impact": 9200,
      "reason_codes": ["high_forecast_occupancy", "event_demand", "competitor_rate_support"],
      "supporting_factors": ["Adjusted occupancy forecast peak: 91.4%", "Competitor ADR: $315"],
      "risk_flags": ["Rate increase capped at configured guardrail (12%)"],
      "status": "proposed"
    }
  ]
}
```

---

## Key Metrics

| Metric | Description |
|--------|-------------|
| Occupancy % | Occupied rooms / Total rooms |
| ADR | Average Daily Rate (revenue / occupied rooms) |
| RevPAR | Revenue Per Available Room (ADR × occupancy) |
| Available Rooms | Total rooms − occupied rooms |
| Demand Trend | 30-day rolling demand index |

---

## Running Tests

**Backend** (83 tests across 4 test files):
```bash
cd backend
python -m pytest -v
```

**Frontend** (17 tests):
```bash
cd frontend
npm test
```

---

## Demo Scenario (Key Feature Demo)

1. **Start the app**: `docker compose up --build`
2. **Open**: http://localhost:5173
3. **Select a hotel** with active demand events (all seeded hotels have them)
4. **View Recommended Commercial Actions** section at the bottom of the dashboard
5. **Observe**: The engine detects demand events raising adjusted occupancy above 85%, and immediately recommends:
   - A guarded rate increase (e.g. +8%, capped at 12%)
   - An event-linked package (parking / late checkout depending on event type)
   - Premium inventory protection if premium rooms are scarce
6. **Click any recommendation card** to expand the detail view showing:
   - Supporting demand signals
   - Reason codes
   - Applied guardrails
   - Estimated revenue impact (labelled as estimate)
7. **Use filters**: Click "Pricing", "Package", "Operational" tabs to filter by category; use the priority dropdown for "High" / "Critical" actions
8. **Verify non-fatal**: If you stop the backend while the frontend is running, recommendations show an error banner but forecast and demand panels continue working

---

## Extension Points

The architecture is designed for incremental AI capability addition:

| Component | Current | Future |
|-----------|---------|--------|
| **Forecasting Engine** | `SeasonalBaselineForecastService` | `TimesFMForecastService` |
| **Event Engine** | `RuleBasedEventEngineService` | `MLEventEngineService` |
| **Recommendation Engine** | `RuleBasedRecommendationService` | `OptimiserRecommendationService` (OR-Tools / RL) |
| **Market Signals** | `MockMarketSignalService` | `LiveRateShopMarketSignalService` |

To swap any engine: change **one factory function** in `app/core/dependencies.py`. No API, schema, or frontend changes required.

### How a Future Optimiser Would Replace the Rule Engine

1. Create `OptimiserRecommendationService` implementing `RecommendationService` (same interface as the rule-based engine)
2. The optimiser receives the same structured inputs (forecast, adjusted forecast, events, metrics, market signals)
3. It can call OR-Tools for price optimisation, or a TimesFM-guided demand model
4. Return the same `RecommendationResponse` — the API and frontend are unaffected
5. Change `get_recommendation_service()` in `dependencies.py` to return the new implementation

---

## Known Limitations (PoC)

- Recommendations are **generated on-demand**, not persisted — no approval workflow yet
- Market signals are **mocked** — no real rate-shopping API integration
- Guardrail values are hardcoded defaults — production would read from a config store
- No multi-property portfolio view — one hotel selected at a time
- Financial impact estimates are **rough PoC-level calculations**, not revenue management models
