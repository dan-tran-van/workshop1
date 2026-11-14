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

The app uses the existing restaurant list/search, restaurant detail, analysis, and sync endpoints. The API's CORS configuration already allows the default Vite origin.

## End-to-end tests

The Playwright suite is based on the cases in `tests/test-cases/`. It mocks the API so the UI tests are repeatable and do not require a running backend.

```bash
npm install
npx playwright install chromium
npm run test:e2e
```

The suite covers listing/search, restaurant details and reviews, AI analysis, and responsive/accessibility checks. FE-06, FE-10, and FE-19 are skipped in Playwright because the current UI does not provide restaurant pagination, review pagination, or analysis history. FE-11 is also skipped and remains deferred until the frontend supports URL-routed restaurant details.
