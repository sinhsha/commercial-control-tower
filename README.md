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
│   │   └── repositories/     # Data access layer
│   └── tests/
├── frontend/                 # React + TypeScript app (Vite)
│   └── src/
│       ├── components/       # Dashboard, UI primitives, Charts
│       ├── hooks/            # Custom React hooks
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

## Key Metrics

| Metric | Description |
|--------|-------------|
| Occupancy % | Occupied rooms / Total rooms |
| ADR | Average Daily Rate (revenue / occupied rooms) |
| RevPAR | Revenue Per Available Room (ADR × occupancy) |
| Available Rooms | Total rooms − occupied rooms |
| Demand Trend | 30-day rolling demand index |

## Extension Points

The architecture is designed for incremental AI capability addition:

- **Forecasting Engine** → `backend/app/services/forecasting_service.py`
- **Price Optimisation** → `backend/app/services/optimization_service.py`
- **AI Explanation** → `backend/app/services/explanation_service.py`
- **ML Models** → `backend/app/ml/` (add as needed)
