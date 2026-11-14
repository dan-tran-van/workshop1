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
