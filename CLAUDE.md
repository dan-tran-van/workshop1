# Claude Code Guidelines (workshop1)

Repository guidelines and commands for Claude Code agents.

## Quick Commands

```bash
# Docker local development (Recommended)
docker compose up --build
docker compose run --rm seed
docker compose run --rm test
docker compose down

# Run unit tests locally
./api/.venv/bin/python -m unittest discover -s api/tests -v

# Run development server locally
cd api && ./venv/bin/uvicorn app.main:app --reload --port 8000

# Seed SQLite database locally
./api/.venv/bin/python api/seed.py

# Install dependencies locally
cd api && pip install -r requirements.txt
```

## Architecture & Codebase

- **Backend (`api/`)**: FastAPI + SQLAlchemy 2.0 + SQLite (`data.db`).
  - `app/models.py`: SQLAlchemy models (`User`, `Restaurant`, `Review`, `Analysis`, `SyncTarget`, `SyncRun`, `Notification`).
  - `app/schemas.py`: Pydantic v2 schemas.
  - `app/services/analysis.py`: OpenAI review sentiment & aspect breakdown analysis with caching and heuristic fallback.
  - `app/services/sync.py`: Google Places review sync with mock support.
  - `app/services/notifications.py`: bad review notifications, recorded after a successful sync for new Google reviews rated at or below `BAD_REVIEW_RATING_THRESHOLD`.
  - `app/services/auth.py` and `app/routers/auth.py`: password hashing, bearer tokens, role checks, and admin user management.
  - `app/routers/`: Modular route handlers (`auth.py`, `restaurants.py`, `reviews.py`, `sync.py`, `notifications.py`).
  - `seed.py`: Realistic seed data generator.
- **Frontend (`frontend/`)**: React + TypeScript dashboard with role-based login and navigation.

## Coding Conventions

- **Python Version**: 3.12+
- **Type Annotations**: Enforce explicit type hints on all function arguments and return types.
- **Error Handling**: Use `fastapi.HTTPException` with explicit HTTP status codes (`status.HTTP_404_NOT_FOUND`, etc.).
- **Async/Sync**: SQLAlchemy session is synchronous (`SessionLocal`), so route handlers interacting with the DB can be standard `def` functions (FastAPI runs them in threadpools) or handle sessions carefully if async.
- **AI Calling**: Always wrap OpenAI API calls with try/except and fallback to `generate_mock_analysis` so the server never crashes on missing keys or network errors.

## Git & PR Guidelines

- Follow Conventional Commits: `feat(api): ...`, `fix(api): ...`, `docs: ...`, `test: ...`.
- Run tests before any commit: `./api/.venv/bin/python -m unittest discover -s api/tests -v`.
- Never stage `.env` or `*.db` files.
