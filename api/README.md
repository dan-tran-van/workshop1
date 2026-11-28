# Restaurant Review Insights — API Backend

A FastAPI backend powered by SQLite (and SQLAlchemy) providing restaurant review collection, sync jobs, and AI-powered actionable improvement suggestions.

---

## Features

- **Restaurant & Review Management**: List, search, and view detailed restaurant profiles with Google reviews.
- **Review Vector Store**: Persist generated review embeddings in the application database and retrieve reviews or rank restaurants by cosine similarity, optionally limited to specific restaurants. Retrieval and centroid computation ignore embeddings when their source review text has changed (`content_hash`). Similarity scans matching stored vectors in-process; no external vector database or ANN index is required. Use `backfill_embeddings.py` (or `docker compose run --rm backfill-embeddings`) to bulk-index existing reviews.
- **AI Review Intelligence**:
  - Overall sentiment & rating trend estimation.
  - Aspect breakdown across 6 core aspects: `food`, `service`, `wait_time`, `hygiene`, `ambience`, `price` (bilingual English + Vietnamese keyword detection).
  - Prioritized actionable improvement steps and key strengths for marketing.
  - **Two-Stage Hybrid Context Compression**: Handles large review datasets (1k–10k+ reviews) with 100% data coverage by combining an $O(N)$ deterministic statistical engine with high-signal stratified sampling (capturing pain points, praises, and recency), reducing token context by 98%+ while executing in ~1.5s with a single LLM call. See [detailed architecture](docs/analysis-context-compression.md).
  - Automatic analysis caching for instant loading and low token costs.
  - Intelligent fallback analyzer if OpenAI API key is not configured.
- **Analysis Read Aloud**: Generate audio with the OpenAI Speech API by default, or use a Kokoro endpoint. Both options keep the same protected API endpoint and cache generated audio in memory.
- **Sync Jobs**:
  - Google Places API integration (`place_id` lookups) with mock fallback for local testing.
  - Tracking of `sync_targets` and `sync_runs`.
- **Bad Review Notifications**:
  - After every successful sync (manual `POST /sync/run` or a scheduled run), each new Google review rated at or below `BAD_REVIEW_RATING_THRESHOLD` (default `2.0`) is recorded in `notifications` and logged as a warning.
  - Failed syncs, mock data, and reviews already notified never create notifications; a notification error never fails the sync.
  - `GET /notifications` lists them with the review attached. Owners only see their assigned restaurants.
- **Role-based access control**:
  - `OWNER`: can access assigned restaurants and their reviews/analysis, and add restaurants to their own account.
  - `ANALYST` (F&B Analyst): can read all restaurant data and run analyses; cannot change source data, manage users, or sync.
  - `ADMIN`: full access, including user provisioning and sync controls.
  - Password-hashed accounts, expiring signed bearer tokens, and server-side authorization on every protected API route.

---

## Database Schema

```text
Core Tables:
- restaurants (id, google_place_id, name, address, google_rating, user_rating_count, last_synced_at, updated_at)
- reviews     (id, restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
- review_embeddings (id, review_id, model, dimensions, embedding, content_hash, created_at, updated_at) — unique per (review_id, model)
- analyses    (id, restaurant_id, overall_sentiment, result_json, review_count, last_review_at, model, created_at)
- analysis_runs (id, user_id, analysis_id, created_at) — authenticated analysis requests, including cache hits

Sync Tables:
- sync_targets (id, target_type, value, language_code, is_active, last_synced_at)
- sync_runs    (id, status, started_at, finished_at, restaurants_upserted, reviews_upserted, error_message)

Notification Tables:
- notifications (id, restaurant_id, review_id, sync_run_id, channel, status, error_message, created_at, sent_at) — unique per (review_id, channel)

Access Tables:
- users (id, email, full_name, password_hash, role, is_active, created_at)
- user_restaurants (user_id, restaurant_id) — restaurant ownership assignments
```

### Analysis results and user history

`analyses` stores generated result snapshots for a restaurant and remains the
shared cache source. `analysis_runs` stores each authenticated user's successful
request for an analysis: the user, the snapshot returned, and the request time.
Despite its name, an `analysis_runs` row does not necessarily mean the AI ran;
a cache hit also creates a row. Multiple history entries, including entries
from different users, can therefore point to the same analysis snapshot.

`GET /auth/me/analysis-history` returns the authenticated user's entries,
newest first, as objects containing the history-entry `id`, `created_at`, and
nested `analysis`. OWNER history only includes restaurants currently assigned
to that owner. Failed analysis requests do not create history entries.

---

## Getting Started

### Using Docker Compose (Quickest)

From the project root:

```bash
# 1. Start backend with live hot-reloading
docker compose up --build

# 2. In another terminal, seed initial data
docker compose run --rm seed

# 3. Run test suite
docker compose run --rm test
```

### Local Virtual Environment

#### 1. Set Up Virtual Environment

```bash
cd api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 2. Environment Configuration

Copy `.env.example` to `.env` and set your API keys (optional for initial local dev):

```bash
cp ../.env.example .env
```

Key variables:
- `DATABASE_URL`: `sqlite:///./data.db`
- `OPENAI_API_KEY`: Your OpenAI API key (falls back to heuristic analysis if omitted)
- `OPENAI_MODEL`: `gpt-4o-mini`
- `TTS_PROVIDER`: `openai` by default; set to `kokoro` to use a Kokoro `/v1/audio/speech` endpoint
- `TTS_BASE_URL`: Base URL for the Kokoro endpoint (required by that provider)
- `TTS_MODEL` / `TTS_VOICE`: `kokoro` / `af_heart` by default for Kokoro
- `TTS_ENDPOINT_TIMEOUT`: `30` seconds by default for Kokoro
- `OPENAI_TTS_MODEL`: `gpt-4o-mini-tts` by default
- `OPENAI_TTS_VOICE`: `coral` by default
- `OPENAI_TTS_TIMEOUT`: `30` seconds by default
- `OPENAI_EMBEDDING_MODEL`: `text-embedding-3-small`
- `GOOGLE_PLACES_API_KEY`: Google Places API Key (optional)
- `AUTH_SECRET_KEY`: stable random signing key for access tokens; set this in deployments so restarts do not invalidate sessions.
- `AUTH_BOOTSTRAP_KEY`: one-time key required to create the first administrator. Set a unique value before opening the app, then use it once on the initial setup screen.
- `BAD_REVIEW_NOTIFICATIONS_ENABLED`: `true` by default; set `false` to stop recording bad review notifications.
- `BAD_REVIEW_RATING_THRESHOLD`: `2.0` by default; new Google reviews rated at or below this value create a notification.

The Dashboard's **Read aloud** button calls
`POST /restaurants/{restaurant_id}/analyses/{analysis_id}/tts`. It uses OpenAI by
default and requires `OPENAI_API_KEY`; alternatively, set `TTS_PROVIDER=kokoro` and configure
`TTS_BASE_URL` for the Kokoro endpoint. Provider selection is explicit: an OpenAI error does not
silently switch to the other provider. Both preserve the existing authentication
and restaurant-access checks. The voice is AI-generated, not a human voice.
OpenAI currently lists `gpt-4o-mini-tts` for shutdown on January 6, 2027; this
model is used for the current educational demo and should be revisited before
that date if the demo remains in use.

The first account is provisioned through the one-time `/auth/bootstrap` endpoint; public self-registration is disabled. Choose a password of at least 12 characters. Administrators can create and deactivate accounts and assign restaurant IDs to owners from the **User access** screen. Use unique, private keys in deployed environments.

### Business workflow and local demo accounts

1. An operator configures the auth keys and bootstraps the first Admin once.
   Remove `AUTH_BOOTSTRAP_KEY` after setup.
2. An Admin seeds or syncs locations and reviews, creates staff accounts, and
   assigns each Owner only the locations they manage.
3. Owners monitor their assigned restaurants and run analysis. F&B Analysts
   compare all restaurants and run analysis but cannot manage users, change
   source reviews, or sync. Admins manage access and sync operations.

For a local demonstration, seed one account per role after at least one
restaurant exists:

```bash
# From the running Docker API container:
docker compose exec api python seed_demo_users.py

# Or from api/ with the local virtual environment and api/.env configured:
python seed_demo_users.py
```

The script uses distinct randomly generated passwords, prints them once, and
assigns the Owner to the first restaurant by ID. Save the passwords privately.
It refuses to overwrite existing demo accounts and is not intended for
production. It does not modify existing users.

#### 3. Seed Sample Data

Populate the database with sample restaurants and reviews:

```bash
python seed.py
```

Optionally backfill review embeddings for semantic competitor lookup (requires `OPENAI_API_KEY`):

```bash
# Local virtualenv (all restaurants):
python backfill_embeddings.py

# Or via Docker Compose from repo root:
docker compose run --rm backfill-embeddings
docker compose run --rm backfill-embeddings --restaurant-id 1
docker compose run --rm backfill-embeddings --review-id 10 --review-id 11
```

#### 4. Run the Development Server

```bash
uvicorn app.main:app --reload --port 8000
```

- API Base URL: `http://localhost:8000`
- Interactive Swagger Docs: `http://localhost:8000/docs`
- Redoc Documentation: `http://localhost:8000/redoc`

---

## Running Tests

The tests create their own temporary SQLite databases, override the FastAPI
database dependency, and mock external providers. No seed data, internet access,
or API credentials are needed to execute tests after installing dependencies.

```bash
# Using Docker from repo root:
docker compose run --rm test

# Or using local Python venv from api directory:
python -m unittest discover -s tests -v

# Or from repository root:
./api/.venv/bin/python -m unittest discover -s api/tests -v
```

Use Python 3.12 or later. On Windows, activate with `.venv\Scripts\Activate.ps1`.
All 25 acceptance cases (17 P0, 8 P1) and reporting tests pass with a 100% success rate.

The **Backend checklist tests** GitHub Actions workflow runs manually using
`workflow_dispatch`, with `all`, `p0`, and `p1` suite choices. It publishes the
test log, JUnit XML, JSON results, a per-case summary, and installed dependency
versions. See [test coverage and documentation](tests/README.md).

---

## API Endpoints Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/restaurants` | List restaurants (supports `?q=search_term`) |
| `GET` | `/restaurants/{id}` | Restaurant detail with reviews and latest analysis |
| `POST` | `/restaurants` | Create a new restaurant |
| `POST` | `/restaurants/{id}/analyze` | Run or retrieve cached AI review analysis |
| `GET` | `/restaurants/{id}/analyses` | History of past analyses for restaurant |
| `GET` | `/auth/me/analysis-history` | The authenticated user's successful analysis requests, including cache hits |
| `GET` | `/restaurants/{id}/reviews` | List reviews for a restaurant |
| `GET` | `/reviews/search` | Semantic review search using stored embeddings with `ILIKE` keyword fallback (`?q=...&restaurant_id=...`) |
| `GET` | `/restaurants/{id}/competitors` | Suggested competitive set ranked by review embedding similarity (when indexed) with review-volume fallback, reasons, and pinned/manual/dismissed choices (Owner, Analyst) |
| `GET` | `/restaurants/{id}/competitors/candidates` | Workspace restaurants that can be added manually as competitors, combining lexical name/address search with semantic review matching when embeddings exist (Owner, Analyst) |
| `PUT` | `/restaurants/{id}/competitors/{competitor_id}` | Pin, dismiss, or manually add a competitor: `{"status": "PINNED" \| "DISMISSED" \| "MANUAL"}` (Owner) |
| `DELETE` | `/restaurants/{id}/competitors/{competitor_id}` | Reset a competitor back to a plain suggestion (Owner) |
| `GET` | `/restaurants/{id}/competitors/gap` | Criteria gap table against the competitive set (Owner, Analyst) |
| `POST` | `/restaurants/{id}/competitors/gap/{aspect}/explain` | Review-grounded explanation with 2-3 quotes; 422 when the criterion lacks data (Owner, Analyst) |
| `POST` | `/restaurants/{id}/reviews` | Add a review |
| `GET` | `/sync/targets` | List sync targets |
| `POST` | `/sync/targets` | Add sync target |
| `POST` | `/sync/run` | Execute sync job |
| `GET` | `/sync/runs` | List sync job execution history |
| `GET` | `/notifications` | Bad review notifications with the review attached (supports `?restaurant_id=`, `skip`, `limit`; Owners see assigned restaurants only) |
| `GET` | `/health` | API health check |
| `GET` | `/auth/setup` | Check whether first-admin setup is required |
| `POST` | `/auth/bootstrap` | Create the first admin with the configured setup key |
| `POST` | `/auth/login` | Exchange email/password for a bearer token |
| `GET` | `/auth/me` | Return the authenticated user and role |
| `GET/POST` | `/admin/users` | List or provision accounts (Admin only) |
| `PATCH` | `/admin/users/{id}` | Change role, account status, or owner restaurant assignments |

Protected endpoints require `Authorization: Bearer <access_token>`. Restaurant ownership violations return 404 to avoid disclosing restaurants outside an owner's account; role violations return 403.
| `GET` | `/auth/setup` | Check whether first-admin setup is required |
| `POST` | `/auth/bootstrap` | Create the first admin with the configured setup key |
| `POST` | `/auth/login` | Exchange email/password for a bearer token |
| `GET` | `/auth/me` | Return the authenticated user and role |
| `GET/POST` | `/admin/users` | List or provision accounts (Admin only) |
| `PATCH` | `/admin/users/{id}` | Change role, account status, or owner restaurant assignments |

Protected endpoints require `Authorization: Bearer <access_token>`. Restaurant ownership violations return 404 to avoid disclosing restaurants outside an owner's account; role violations return 403.
