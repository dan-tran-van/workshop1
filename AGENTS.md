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
- **Frontend** *(Upcoming)*: To be housed under `frontend/`

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
│   │   ├── routers/          # Route handlers (restaurants.py, reviews.py, sync.py)
│   │   └── services/         # Business logic (analysis.py, sync.py)
│   ├── tests/
│   │   └── test_api.py       # API integration tests
│   ├── seed.py               # Seed script with realistic restaurant & review data
│   ├── requirements.txt      # Python dependencies
│   ├── .env.example          # Environment template
│   └── README.md             # API documentation
├── frontend/                 # Client UI application (future expansion)
├── .github/
│   └── pull_request_template.md
├── AGENTS.md                 # Agent coding guide (this file)
├── CLAUDE.md                 # Claude Code CLI instructions
├── CONTRIBUTING.md           # Contributor guidelines
└── README.md                 # Main project readme & collaboration guide
```

---

## 4. Key Commands for Agents

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
./api/.venv/bin/python -m unittest api/tests/test_api.py

# Or from within api/
cd api && python -m unittest tests/test_api.py
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

2. **Schema & Model Separation**:
   - Database tables must be defined in `app/models.py`.
   - Data validation and serialization schemas must be defined in `app/schemas.py`.
   - Always use Pydantic v2 `ConfigDict(from_attributes=True)` for ORM compatibility.

3. **Resilient AI Calling**:
   - Never let an OpenAI API outage or missing API key crash the application.
   - Always preserve the heuristic fallback analyzer in `app/services/analysis.py` for offline/mock environments.
   - Always check for cached analyses before triggering an LLM call unless explicitly instructed with `force_refresh=True`.

4. **Database Conventions**:
   - SQLite tables use `autoincrement=True` integer primary keys.
   - Relationships cascade properly (`cascade="all, delete-orphan"` where appropriate).
   - Foreign keys must be indexed for query performance.

5. **Security & Cleanliness**:
   - Never commit `.env`, `data.db`, `*.sqlite`, or API keys into git.
   - Ensure CORS origins remain configurable via `app/config.py`.

---

## 6. Git & Commit Expectations

- **Branch naming**: `feat/<name>`, `fix/<name>`, `docs/<name>`, `test/<name>`, `refactor/<name>`.
- **Commit style**: Conventional Commits (e.g., `feat(api): add export endpoint for analysis`).
- **Pre-commit checklist**:
  - [ ] All tests pass: `python -m unittest api/tests/test_api.py`.
  - [ ] New endpoints have corresponding test coverage.
  - [ ] No temporary files or SQLite databases staged.
