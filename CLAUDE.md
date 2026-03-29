# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-Powered Mutual Fund Advisory & Portfolio Intelligence System — an institutional-grade financial planning platform combining quantitative engines (MPT, Monte Carlo), real-time macroeconomic signals, and explainable AI recommendations.

## Commands

### Running the System

```bash
# Backend API (FastAPI)
uvicorn backend.main:app --reload
# Available at http://localhost:8000

# Frontend (Streamlit)
streamlit run frontend/app.py
# Available at http://localhost:8501

# Celery worker (async AI agents)
celery -A ai_agents.tasks worker --loglevel=info
```

### Tests

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_core_logic.py -v

# Run with coverage
pytest --cov=backend --cov=ai_layer --cov=ai_agents

# Run phase-based integration tests
python tests/run_all_phase_tests.py
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Architecture

The system has four layers:

### 1. API Layer (`backend/api/main.py`)
FastAPI REST API with JWT auth. Handles client CRUD, proposal persistence, risk/goal/allocation calculations, and audit logging. All endpoints route through versioned engines based on feature flags in `config.py`.

### 2. Quantitative Engines (`backend/engines/`)
Versioned engines with v1/v2 routing via feature flags:
- **Risk Engine** — Multi-factor risk profiling, behavioral normalization, XAI explanations
- **Goal Engine** — Lifecycle goal planning (retirement, education, marriage, real estate, emergency fund)
- **Allocation Engine** — MPT optimization via SciPy; volatility constraints map risk score (0–10) to target vol (4%–20%); structural bounds enforced (15% max gold, 35% max bonds/debt)
- **Monte Carlo Engine** — 1000+ iteration GBM simulations for success probability
- **Investment Mode Engine** — Smart deployment recommendations (SIP, Lumpsum, STP, SWP) based on market conditions
- **Recommendation Engine** — Fund selection by category and risk profile

### 3. AI Intelligence Layer (`ai_layer/`)
Async, macro-aware intelligence. `ai_layer/__init__.py` is the public orchestration API:
- **Signal Engine** — Generates market signals from FRED macroeconomic data and FBIL repo rates
- **Scoring Engine** — Re-scores funds in real-time based on market regime
- **Decision Engine** — Applies portfolio tilts (equity overweight/underweight) based on macro regime
- **Data Ingestion** — Fetches live data: AMFI NAVs, yfinance prices, FRED macro indicators
- **Scheduler** — APScheduler periodic updates, results cached in `data/cache/` JSON files

### 4. Async Agent Orchestration (`ai_agents/`)
Celery-based pipeline with Redis as broker. Task flow: `market_agent → signal_agent → prediction_agent → decision_agent → storage`. Retry logic with exponential backoff.

### 5. Frontend (`frontend/`)
Streamlit dashboard communicating with backend via `frontend/api_client.py`. Components in `frontend/components/` include risk meter, goal projection panels, SIP calculator, and portfolio gap advisor.

## Feature Flags (`config.py`)

Engine routing is controlled by `FEATURE_FLAGS`:
```python
FEATURE_FLAGS = {
    "v2_risk_explanation": True,       # Risk Engine v2 vs v1
    "advanced_goal_types": True,       # Goal Engine v2 vs v1
    "investment_mode_recommendation": True,  # Smart mode recommendation
    "advanced_products": False,        # Future extension point
}
EXCLUDE_ETF_FROM_ADVISORY = True
```

## Database

PostgreSQL (Neon Cloud) via SQLAlchemy ORM. Key models in `backend/database/models.py`:
- `Advisors`, `Clients` — user and client management
- `RiskQuestionnaires`, `GoalLines`, `PortfolioSnapshots` — financial profile data
- `ProposalDrafts` — system-generated vs advisor-overridden proposals
- `AuditLogs` — complete change history with before/after values

`DATABASE_URL`, `SECRET_KEY`, `ADMIN_SECRET`, and `ENVIRONMENT` are configured in `.env`.

## Key Patterns

- **Engine versioning**: v1 engines in `backend/engines/v1/`, v2 in `backend/engines/v2/`. Top-level engine files (e.g. `risk_engine.py`, `goal_engine.py`) act as routers that delegate based on feature flags.
- **Market-aware adaptation**: Macro indicators (inflation, repo rate, bond yields, Nifty P/E, VIX) drive allocation tilts and deployment guardrails at market peaks.
- **XAI**: Risk scores are decomposed by factor contribution and narrated via `backend/engines/v2/explanation_standards.py` and `ai_layer/explanation_engine/`.
- **Caching**: Market/macro/signal data cached as JSON in `data/cache/` (auto-refreshed by the scheduler).
