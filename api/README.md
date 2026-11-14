# Restaurant Review Insights — API Backend

A FastAPI backend powered by SQLite (and SQLAlchemy) providing restaurant review collection, sync jobs, and AI-powered actionable improvement suggestions.

---

## Features

- **Restaurant & Review Management**: List, search, and view detailed restaurant profiles with Google reviews.
- **AI Review Intelligence**:
  - Overall sentiment & rating trend estimation.
  - Aspect breakdown: `food`, `service`, `wait_time`, `hygiene`, `ambience`, `price`.
  - Prioritized actionable improvement steps and key strengths for marketing.
  - Automatic analysis caching for instant loading and low token costs.
  - Intelligent fallback analyzer if OpenAI API key is not configured.
- **Sync Jobs**:
  - Google Places API integration (`place_id` lookups) with mock fallback for local testing.
  - Tracking of `sync_targets` and `sync_runs`.

---

## Database Schema

```text
Core Tables:
- restaurants (id, google_place_id, name, address, google_rating, user_rating_count, last_synced_at, updated_at)
- reviews     (id, restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
- analyses    (id, restaurant_id, overall_sentiment, result_json, review_count, last_review_at, model, created_at)

Sync Tables:
- sync_targets (id, target_type, value, language_code, is_active, last_synced_at)
- sync_runs    (id, status, started_at, finished_at, restaurants_upserted, reviews_upserted, error_message)
```

---

## Getting Started

### 1. Set Up Virtual Environment

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and set your API keys (optional for initial local dev):

```bash
cp .env.example .env
```

Key variables:
- `DATABASE_URL`: `sqlite:///./data.db`
- `OPENAI_API_KEY`: Your OpenAI API key (falls back to heuristic analysis if omitted)
- `OPENAI_MODEL`: `gpt-4o-mini`
- `GOOGLE_PLACES_API_KEY`: Google Places API Key (optional)

### 3. Seed Sample Data

Populate the database with sample restaurants and reviews:

```bash
python seed.py
```

### 4. Run the Development Server

```bash
uvicorn app.main:app --reload --port 8000
```

- API Base URL: `http://localhost:8000`
- Interactive Swagger Docs: `http://localhost:8000/docs`
- Redoc Documentation: `http://localhost:8000/redoc`

---

## Running Tests

Run the test suite:

```bash
python -m unittest api/tests/test_api.py
```

---

## API Endpoints Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/restaurants` | List restaurants (supports `?q=search_term`) |
| `GET` | `/restaurants/{id}` | Restaurant detail with reviews and latest analysis |
| `POST` | `/restaurants` | Create a new restaurant |
| `POST` | `/restaurants/{id}/analyze` | Run or retrieve cached AI review analysis |
| `GET` | `/restaurants/{id}/analyses` | History of past analyses for restaurant |
| `GET` | `/restaurants/{id}/reviews` | List reviews for a restaurant |
| `POST` | `/restaurants/{id}/reviews` | Add a review |
| `GET` | `/sync/targets` | List sync targets |
| `POST` | `/sync/targets` | Add sync target |
| `POST` | `/sync/run` | Execute sync job |
| `GET` | `/sync/runs` | List sync job execution history |
| `GET` | `/health` | API health check |
