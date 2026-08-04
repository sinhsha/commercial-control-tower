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
│   │   │   ├── recommendations/  # Commercial recommendation engine
│   │   │   ├── ancillaries/      # Ancillary Revenue Engine
│   │   │   └── copilot/          # Grounded LLM Explanation Service ← NEW
│   │   └── repositories/     # Data access layer
│   └── tests/
├── frontend/                 # React + TypeScript app (Vite)
│   └── src/
│       ├── components/       # Dashboard, UI primitives, Charts
│       │   └── dashboard/    # RecommendationCard, AncillaryCard, AncillaryPanel, TotalRevenueBar, CopilotPanel ← NEW
│       ├── hooks/            # Custom React hooks (useAncillaryRecommendations, useCopilot ← NEW)
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

## 6 · Ancillary Revenue Optimization + Next-Best-Offer Engine

A deterministic rule-based engine for 20 ancillary products across 9 categories.

### Products Catalog (20 products)
| Code | Category | Base Price | Tier |
|------|----------|-----------|------|
| PARKING | Parking & Transport | $42 | High |
| VALET | Parking & Transport | $28 | Medium |
| EV_CHARGING | Parking & Transport | $18 | Medium |
| SPA_BOOKING | Spa & Wellness | $120 | High |
| MEETING_SMALL | Meetings & Events | $225 | High |
| DAY_USE_ROOM | Room Inventory | $99 | High |
| WORKSPACE | Workspace | $55 | High |
| FB_DIGITAL | Food & Beverage | $38 | High |
| … | … | … | … |

### Engine Pipeline
1. **Context Builder** — loads hotel metrics, forecast, and events from DB
2. **Eligibility** — suppresses ineligible products (capacity, persona, flags, margin)
3. **Dynamic Pricing** — demand/event/utilization signals adjust prices (guardrailed at ±20%/±15%)
4. **Propensity Scoring** — deterministic formula: base\_rate + segment\_affinity + event\_boost + stay\_length + demand + capacity
5. **Opportunity Scoring** — composite score: propensity×30 + margin×25 + demand×20 + segment×15 + event×7 + capacity×3
6. **Rank & Limit** — top N by score

### Guest Personas (8)
`hotel_wide` · `business_traveler` · `conference_attendee` · `leisure_couple` · `family` · `resort_guest` · `ev_traveler` · `pet_traveler`

### Ancillary Guardrails
| Guardrail | Default |
|-----------|---------|
| `max_ancillary_price_increase_pct` | 20% |
| `max_ancillary_price_decrease_pct` | 15% |
| `minimum_margin_pct` | 25% |
| `maximum_offer_count` | 5 |
| `minimum_propensity_threshold` | 10% |
| `suppress_at_capacity_pct` | 95% |

---

## 7 · Revenue Manager Copilot / Grounded Explanation Service ← NEW

A grounded LLM explanation layer built on top of the deterministic engines.

### What the Copilot Does
| Surface | Description |
|---------|-------------|
| **Executive Summary** | 3–5 sentence GM-level narrative synthesising room + ancillary opportunity |
| **Commercial Explanation** | 2–4 sentence explanation of a specific commercial action |
| **Ancillary Explanation** | 2–3 sentence explanation of a ranked ancillary offer |
| **Q&A** | Free-form revenue manager question answered with grounded context |

### Grounding Contract
The LLM is **never** given open access to the internet or unvalidated input.  Every prompt is assembled exclusively from structured data produced by the deterministic engines:
- Hotel metrics (occupancy, ADR, RevPAR)
- Forecast occupancy (baseline + event-adjusted)
- Active demand events (name, type, attendance, distance)
- Commercial recommendation context (title, action, revenue impact, reason codes)
- Ancillary recommendation context (name, rank, pricing, propensity, margin)

The existing **ExplainabilityPanel** (demand-event adjustment rationale) is **not replaced, duplicated, or modified** — it remains fully deterministic.

### Graceful Degradation
If `OPENAI_API_KEY` is not configured (or `COPILOT_ENABLED=false`), all copilot endpoints return structured fallback text built from the grounding data alone. All other dashboard panels are unaffected.

### Configuration
```bash
# .env
OPENAI_API_KEY=sk-...          # Leave empty to disable; fallback text still returned
OPENAI_MODEL=gpt-4o-mini       # Any Chat Completions model
COPILOT_ENABLED=true
COPILOT_MAX_TOKENS=400
```

### To Swap LLM Provider
1. Subclass `CopilotService` (`app/services/copilot/base.py`) and implement the four abstract methods.
2. Change `get_copilot_service()` in `app/core/dependencies.py` to return the new implementation.
3. No API, schema, or frontend changes required.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/hotels/{id}/recommendations` | List ranked commercial recommendations |
| GET | `/api/v1/hotels/{id}/recommendations/{rec_id}` | Single recommendation detail |
| GET | `/api/v1/hotels/{id}/ancillaries` | Full ancillary product catalog |
| GET | `/api/v1/hotels/{id}/ancillary-recommendations` | Ranked ancillary offers |
| GET | `/api/v1/hotels/{id}/ancillary-recommendations/{code}` | Single ancillary detail |
| GET | `/api/v1/hotels/{id}/copilot/executive-summary` | LLM executive summary ← NEW |
| POST | `/api/v1/hotels/{id}/copilot/ask` | Copilot Q&A ← NEW |
| POST | `/api/v1/hotels/{id}/copilot/explain-commercial` | LLM explanation for a recommendation ← NEW |
| POST | `/api/v1/hotels/{id}/copilot/explain-ancillary` | LLM explanation for an ancillary offer ← NEW |
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

**Backend** (155 tests across 7 test files):
```bash
cd backend
python -m pytest -v
```

**Frontend** (33 tests across 2 test files):
```bash
cd frontend
npm test
```

---

## Demo Scenario

### Copilot Demo ← NEW
1. **Start the app**: `docker compose up --build`
2. **Open**: http://localhost:5173 → select a hotel
3. **Scroll to "Revenue Manager Copilot"** (below Ancillary panel)
4. **Observe the Executive Summary** — a 3–5 sentence GM narrative appears automatically, grounded in live occupancy, ADR, forecast, and top commercial + ancillary actions
5. **Try the Q&A chat** — type a question such as:
   - *"Should I raise rates this weekend?"*
   - *"What ancillary offers should I prioritise for conference attendees?"*
   - *"How does the upcoming event affect my revenue strategy?"*
   - Or click a suggestion chip to pre-fill the input
6. **Without an API key** — all responses gracefully fall back to structured text derived from deterministic engine output (no blank panels)
7. **Set `OPENAI_API_KEY=sk-...`** in `.env` and restart → real GPT-4o-mini explanations appear

#### API Demo (copilot)
```bash
# Executive summary
curl "http://localhost:8000/api/v1/hotels/{hotel_id}/copilot/executive-summary?persona=hotel_wide&days=14"

# Q&A
curl -X POST http://localhost:8000/api/v1/hotels/{hotel_id}/copilot/ask \
  -H "Content-Type: application/json" \
  -d '{
    "grounding": {
      "question": "Should I raise rates this weekend?",
      "hotel_name": "Grand Plaza Hotel",
      "as_of_date": "2025-08-01",
      "current_occupancy_pct": 72.5,
      "forecast_occupancy_pct": 84.0,
      "current_adr": 279,
      "competitor_adr": 265,
      "active_events": [],
      "top_commercial_actions": ["Increase Weekend Rate"],
      "top_ancillary_offers": [],
      "room_revenue_opportunity": 18000,
      "ancillary_revenue_opportunity": 7500,
      "persona": "hotel_wide"
    }
  }'
```

---

### Commercial Recommendations Demo
1. **Start the app**: `docker compose up --build`
2. **Open**: http://localhost:5173
3. **Select a hotel** with active demand events (all seeded hotels have them)
4. **View Recommended Commercial Actions** — the engine detects events raising occupancy above 85% and recommends:
   - A guarded rate increase (e.g. +8%, capped at 12%)
   - An event-linked package (parking / late checkout depending on event type)
5. **Click any recommendation card** to expand supporting signals, reason codes, and estimated revenue impact

### Ancillary Revenue Demo ← NEW
6. **View Ancillary Revenue Opportunities** — new section below Recommended Commercial Actions
7. **Observe the Total Revenue Bar** — shows Room Revenue Opportunity + Ancillary Revenue Opportunity + Total (all estimates)
8. **Switch Guest Persona** — use the dropdown to switch between:
   - **Conference Attendee** → Meeting rooms and parking rise to the top
   - **Leisure Couple** → Spa, pool day pass, and experiences dominate
   - **EV Traveler** → EV Charging appears (only persona where it's eligible)
   - **Pet Traveler** → Pet Welcome Program unlocks (gated by pet flag)
   - **Family** → Tours, experiences, parking, and spa appear
9. **Use category tabs** — filter to "Parking", "Spa", "Meetings", etc.
10. **Click any ancillary card** to see:
    - Why this offer (supporting factors + reason codes)
    - Dynamic pricing with reason (e.g. "+10% — High demand & parking utilization")
    - Expected value grid (eligible guests / conversions / revenue / margin — all estimates)
    - Score breakdown (6 mini-bars showing propensity, margin, demand, segment, event, capacity contributions)
11. **Try convention event** — add a convention event in the Event Portal → return to Ancillary panel → confirm Meeting Room and Parking scored higher (event_demand_boost reason code appears)
12. **Verify non-fatal**: ancillary engine errors show an inline error without affecting forecast or demand panels

### API Demo
```bash
# Full catalog
curl http://localhost:8000/api/v1/hotels/{hotel_id}/ancillaries

# Conference attendee recommendations
curl "http://localhost:8000/api/v1/hotels/{hotel_id}/ancillary-recommendations?persona=conference_attendee&limit=5"

# Leisure couple with spa filter
curl "http://localhost:8000/api/v1/hotels/{hotel_id}/ancillary-recommendations?persona=leisure_couple&category=spa_wellness"

# Single product detail
curl "http://localhost:8000/api/v1/hotels/{hotel_id}/ancillary-recommendations/PARKING"
```

---

## Extension Points

The architecture is designed for incremental AI capability addition:

| Component | Current | Future |
|-----------|---------|--------|
| **Forecasting Engine** | `SeasonalBaselineForecastService` | `TimesFMForecastService` |
| **Event Engine** | `RuleBasedEventEngineService` | `MLEventEngineService` |
| **Recommendation Engine** | `RuleBasedRecommendationService` | `OptimiserRecommendationService` (OR-Tools / RL) |
| **Ancillary Engine** | `RuleBasedAncillaryRecommendationService` | `MLAncillaryRecommendationService` |
| **Propensity Scorer** | `PropensityScoringService` (deterministic) | ML propensity model (same interface) |
| **Market Signals** | `MockMarketSignalService` | `LiveRateShopMarketSignalService` |
| **Ancillary Catalog** | `SeededAncillaryCatalogService` | `DBBackedAncillaryCatalogService` |
| **Copilot / LLM** | `OpenAICopilotService` (GPT-4o-mini) | `AnthropicCopilotService` / `WatsonXCopilotService` |

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
