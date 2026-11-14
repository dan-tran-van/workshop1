# Claude Code Guidelines (workshop1)

Repository guidelines and commands for Claude Code agents.

## Quick Commands

```bash
# Run unit tests
./api/.venv/bin/python -m unittest api/tests/test_api.py

# Run development server
cd api && ./venv/bin/uvicorn app.main:app --reload --port 8000

# Seed SQLite database
./api/.venv/bin/python api/seed.py

# Install dependencies
cd api && pip install -r requirements.txt
```

## Architecture & Codebase

- **Backend (`api/`)**: FastAPI + SQLAlchemy 2.0 + SQLite (`data.db`).
  - `app/models.py`: SQLAlchemy models (`Restaurant`, `Review`, `Analysis`, `SyncTarget`, `SyncRun`).
  - `app/schemas.py`: Pydantic v2 schemas.
  - `app/services/analysis.py`: OpenAI review sentiment & aspect breakdown analysis with caching and heuristic fallback.
  - `app/services/sync.py`: Google Places review sync with mock support.
  - `app/routers/`: Modular route handlers (`restaurants.py`, `reviews.py`, `sync.py`).
  - `seed.py`: Realistic seed data generator.
- **Frontend (`frontend/`)**: Client-side UI (pending initialization).

## Coding Conventions

- **Python Version**: 3.12+
- **Type Annotations**: Enforce explicit type hints on all function arguments and return types.
- **Error Handling**: Use `fastapi.HTTPException` with explicit HTTP status codes (`status.HTTP_404_NOT_FOUND`, etc.).
- **Async/Sync**: SQLAlchemy session is synchronous (`SessionLocal`), so route handlers interacting with the DB can be standard `def` functions (FastAPI runs them in threadpools) or handle sessions carefully if async.
- **AI Calling**: Always wrap OpenAI API calls with try/except and fallback to `generate_mock_analysis` so the server never crashes on missing keys or network errors.

## Git & PR Guidelines

- Follow Conventional Commits: `feat(api): ...`, `fix(api): ...`, `docs: ...`, `test: ...`.
- Run tests before any commit: `./api/.venv/bin/python -m unittest api/tests/test_api.py`.
- Never stage `.env` or `*.db` files.
