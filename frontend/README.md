# Gather frontend

React + TypeScript web UI for the Restaurant Review Insights API.

## Run locally

### Option A: Docker Compose (Recommended)

From the project root:

```bash
docker compose up --build
```

Then open `http://localhost:5173`.

### Option B: Local Node.js

1. Start the FastAPI backend at `http://localhost:8000` (see [`../api/README.md`](../api/README.md)).
2. From this directory, install dependencies and start Vite:

   ```bash
   npm install
   npm run dev
   ```

3. Open `http://localhost:5173`.

The API base URL defaults to `http://localhost:8000`. To use another backend URL, set `VITE_API_BASE_URL` in a `.env.local` file before starting Vite.

On first launch, create the initial administrator with the `AUTH_BOOTSTRAP_KEY` configured for the API. Subsequent users sign in with accounts provisioned by an administrator. The dashboard hides role-restricted navigation, while the API independently enforces every permission. Owners only see assigned locations, F&B Analysts can inspect and analyze all locations, and Admins can manage accounts and data sync.

The app uses the restaurant list/search, restaurant detail, analysis, restaurant analysis history (`GET /restaurants/{id}/analyses`), per-user analysis activity (`GET /auth/me/analysis-history`), sync, authentication, and user-management endpoints. The API's CORS configuration already allows the default Vite origin.

When a restaurant has two or more analysis snapshots, the **At a glance** section compares the current 6 criteria (`food`, `service`, `wait_time`, `hygiene`, `ambience`, `price`) against a selectable past snapshot, displaying score deltas, sentiment shifts, baseline progress markers, a comparison summary strip, and a toggleable **Cards / Chart** (SVG radar + paired horizontal bars) view. Users can also launch a comparison directly from older rows in **Review insights → Your analysis activity**.

## End-to-end tests

The Playwright suite is based on the cases in `tests/test-cases/`. It mocks the API so the UI tests are repeatable and do not require a running backend.

```bash
npm install
npx playwright install chromium
npm run test:e2e
```

The suite covers role-specific navigation and comparison access (`ADMIN`, `OWNER`, `ANALYST`), listing/search, restaurant details and reviews, AI analysis, 6-criteria historical comparison (`FE-21`–`FE-25`), per-user analysis activity (`FE-20`), and responsive/accessibility checks. FE-06, FE-10, and FE-19 remain skipped in Playwright (restaurant pagination, review pagination, and a dedicated per-restaurant analysis history region). FE-11 is also skipped and remains deferred until the frontend supports URL-routed restaurant details.
