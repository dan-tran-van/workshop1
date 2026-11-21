# Agent Guidelines for workshop1

This file provides system instructions, technical architecture, and coding conventions for AI agents (Cursor, Copilot, Gemini CLI, Claude, OpenAI, etc.) working on this repository.

---

## 1. Project Context & Objectives

- **Product Name**: Restaurant Review Insights (`workshop1`)
- **Domain**: F&B review intelligence and actionable improvement suggestions.
- **Core Problem**: Restaurant managers receive high volumes of Google Maps reviews but lack time to synthesize root causes.
- **Solution**:
  - Ingest Google Maps reviews for restaurants.
  - Structure customer feedback across 6 core aspects: `food`, `service`, `wait_time`, `hygiene`, `ambience`, `price`.
  - Provide actionable, prioritized recommendations and highlight key strengths for marketing.
  - Cache AI analysis results to minimize LLM token costs and keep response times fast.

---

## 2. Technical Stack

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2.0 (ORM), Pydantic v2, Uvicorn
- **Database**: SQLite (local development in `data.db`, connection string `sqlite:///./data.db` with `check_same_thread=False`)
- **AI / LLM**: OpenAI Chat Completions API (`gpt-4o-mini` default), with a built-in heuristic fallback when `OPENAI_API_KEY` is not provided
- **Testing**: Python standard `unittest` / `unittest.TestCase` with `fastapi.testclient.TestClient`
- **Frontend**: React, TypeScript, Vite under `frontend/`; authenticated role-aware dashboard

---

## 3. Directory Layout

```text
workshop1/
├── api/
│   ├── app/
│   │   ├── config.py         # Pydantic BaseSettings (.env loading)
│   │   ├── database.py       # Engine, SessionLocal, get_db dependency
│   │   ├── models.py         # SQLAlchemy ORM models (restaurants, reviews, analyses, sync_*)
│   │   ├── schemas.py        # Pydantic request/response & analysis payload models
│   │   ├── main.py           # FastAPI app instance, CORS middleware, router registration
│   │   ├── routers/          # Route handlers (auth.py, restaurants.py, reviews.py, sync.py)
│   │   └── services/         # Business logic (analysis.py, auth.py, sync.py)
│   ├── tests/
│   │   ├── test_api.py       # API acceptance and integration tests
│   │   └── test_rbac.py      # Role-based access tests
│   ├── seed.py               # Seed script with realistic restaurant & review data
│   ├── requirements.txt      # Python dependencies
│   ├── .env.example          # Environment template
│   └── README.md             # API documentation
├── frontend/                 # React + TypeScript web application
├── docker-compose.yml        # Docker Compose configuration for local dev
├── .dockerignore             # Docker build ignore rules
├── .env.example              # Environment variables template
├── .github/
│   └── pull_request_template.md
├── AGENTS.md                 # Agent coding guide (this file)
├── CLAUDE.md                 # Claude Code CLI instructions
├── CONTRIBUTING.md           # Contributor guidelines
└── README.md                 # Main project readme & collaboration guide
```

---

## 4. Key Commands for Agents

### Docker (Recommended for Local Dev)
```bash
# Start backend server with hot-reload
docker compose up --build

# Seed initial database
docker compose run --rm seed

# Run unit tests
docker compose run --rm test

# Stop services
docker compose down
```

### Virtual Environment & Dependencies
```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run Tests (Mandatory before submitting changes)
```bash
# Run unit tests from repo root
./api/.venv/bin/python -m unittest discover -s api/tests -v

# Or run discovery across all tests from within api/
cd api && .venv/bin/python -m unittest discover -s tests -v

# Run by priority (P0 or P1)
cd api && .venv/bin/python -m unittest discover -s tests -v -k _p0_
cd api && .venv/bin/python -m unittest discover -s tests -v -k _p1_

# Generate CI markdown and JSON reports
cd api && .venv/bin/python -m unittest discover -s tests -v > reports/unittest.log 2>&1
cd api && .venv/bin/python tests/report_results.py reports/unittest.log --output reports
```

### Seed Local Database
```bash
./api/.venv/bin/python api/seed.py
```

### Run Dev Server
```bash
cd api
uvicorn app.main:app --reload --port 8000
```

---

## 5. Architectural Rules & Best Practices

1. **Keep Routers Thin, Services Fat**:
   - Router endpoints in `app/routers/` should validate input, call service functions, and return responses.
   - Business logic, LLM calling, external HTTP calls, and caching logic belong in `app/services/`.

2. **Schema & Model Separation & Validation**:
   - Database tables must be defined in `app/models.py`.
   - Data validation and serialization schemas must be defined in `app/schemas.py`.
   - Always use Pydantic v2 `ConfigDict(from_attributes=True)` for ORM compatibility.
   - Enforce domain validation bounds: ratings must strictly be between `1.0` and `5.0`.
   - Validate body payload vs URL consistency: review creation endpoints must reject mismatched `restaurant_id` values with HTTP 422.
   - Deduplicate external entities: duplicate external review IDs must return HTTP 409 Conflict rather than throwing unhandled database exceptions.

3. **Resilient AI Calling & Cache Freshness**:
   - Never let an OpenAI API outage or missing API key crash the application.
   - Validate LLM JSON outputs against Pydantic schemas with strict enums; malformed outputs must safely trigger the heuristic mock fallback.
   - Always check for cached analyses before triggering an LLM call unless explicitly instructed with `force_refresh=True`.
   - Cache invalidation: compare `latest_analysis.review_count == review_count` so inserting new or backdated reviews invalidates stale cache snapshots.

4. **Sync Atomicity & Error Handling**:
   - Sync jobs must be atomic: on provider error, timeout, or invalid payloads, execute `db.rollback()` to prevent partial imports.
   - Accurately persist job status as `FAILED`.
   - Never leak internal exception details or provider API keys in API responses.

5. **Database Conventions**:
   - SQLite tables use `autoincrement=True` integer primary keys.
   - Relationships cascade properly (`cascade="all, delete-orphan"` where appropriate).
   - Foreign keys must be indexed for query performance.

6. **Security & Cleanliness**:
   - Never commit `.env`, `data.db`, `*.sqlite`, or API keys into git.
   - Ensure CORS origins remain configurable via `app/config.py`.

---

## 6. Git & Commit Expectations

- **Collaboration Model**: Direct repository collaborator (no forks needed). Always work on a feature branch and open a PR into `main`.
- **Branch naming**: `feat/<name>`, `fix/<name>`, `docs/<name>`, `test/<name>`, `refactor/<name>`.
- **Commit style**: Conventional Commits (e.g., `feat(api): add export endpoint for analysis`).
- **Pre-commit checklist**:
  - [ ] All tests pass: `python -m unittest discover -s api/tests -v`.
  - [ ] New endpoints have corresponding test coverage.
  - [ ] No temporary files or SQLite databases staged.
- **Workflow**:
  1. `git checkout main && git pull origin main`
  2. `git checkout -b feat/<name>`
  3. Work & test: `./api/.venv/bin/python -m unittest discover -s api/tests -v`
  4. `git add . && git commit -m "feat(api): ..."`
  5. `git fetch origin && git rebase origin/main`
  6. `git push -u origin feat/<name>`
  7. Open PR on GitHub: `feat/<name>` -> `main`
