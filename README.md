# Holdings dashboard

Next.js + FastAPI dashboard for Canadian broker CSV exports: allocation, NYSE+TSX calendar data, goal sizing, contribution-adjusted snapshot history, market universes, activity, journal, and deterministic portfolio alerts.

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt

# Terminal 1: Python API
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Next.js frontend
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` for the dashboard. The frontend reads `API_BASE_URL` or `NEXT_PUBLIC_API_BASE_URL` and defaults to `http://localhost:8000`.

Copy `.env.example` to `.env` if you use OpenAI commentary. If you connect a broker via Plaid, also set `PLAID_CLIENT_ID`, `PLAID_SECRET`, and `PLAID_ENV`.

### Local persistence

Vaultboard stores goals, snapshots, activity, journal entries, and broker sync metadata in a local SQLite database named `vaultboard.db`. Set `VAULTBOARD_DB_PATH` to use another location.

If older JSON files such as `portfolio_goals.json`, `portfolio_snapshots.json`, `activity_log.json`, `journal_entries.json`, or `broker_connections.json` exist, the app migrates them into SQLite the first time the matching table is empty. The JSON files are left in place as a backup.

### Upgrade note

This upgrade adds SQLite-backed app state, contribution-adjusted returns, deterministic portfolio alerts, and focused pytest coverage. Existing JSON state files are migrated automatically on first use.

The dashboard also includes allocation views for security type and currency, account/symbol history from stored snapshots, and filters for Activity and Journal.

## Data

Place a holdings CSV path in the sidebar or upload a file. A small sample lives in `data/holdings-report-2026-04-18.csv`.

## Health checks and alerts

GitHub Actions runs `.github/workflows/app-health.yml` on pushes, pull requests, manual dispatch, and every 6 hours. It installs dependencies, runs `pytest`, compiles core modules, imports production modules, checks the Next.js frontend with `npm run typecheck` and `npm run build`, and smoke-builds both Docker images. Enable GitHub email notifications for failed Actions runs to receive alerts when the app health check fails.

## Low-cost deploy: Vercel + Render

For a lower-cost first deployment, host the FastAPI backend on Render and the Next.js frontend on Vercel.

### 1. Deploy the backend on Render

1. Push this branch to GitHub.
2. In Render, create a new **Blueprint** or **Web Service** from this repository.
3. If using the blueprint, Render reads `render.yaml`.
4. If creating the service manually:
   - Root directory: repo root
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - Health check path: `/api/health`
5. Copy the backend URL, for example `https://holdings-api.onrender.com`.

Optional Render environment variables:

- `OPENAI_API_KEY`: only needed for OpenAI commentary.
- `OPENAI_MODEL`: defaults to `gpt-4o-mini`.
- `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV`: only needed for broker integrations.
- `VAULTBOARD_DB_PATH`: defaults to `/tmp/vaultboard.db` in `render.yaml`.
- `CORS_ALLOW_ORIGINS`: set this after Vercel gives you a frontend URL.

Render free services may sleep after inactivity, so the first request after a quiet period can be slow.

### 2. Deploy the frontend on Vercel

1. In Vercel, import the same GitHub repository.
2. Set **Root Directory** to `frontend`.
3. Keep the default Next.js build settings, or use the commands in `frontend/vercel.json`.
4. Add this environment variable:
   - `API_BASE_URL=https://<your-render-backend>.onrender.com`
5. Deploy and copy the Vercel frontend URL, for example `https://holdings-dashboard.vercel.app`.

### 3. Connect CORS

After the Vercel URL exists, update the Render backend environment variable:

```text
CORS_ALLOW_ORIGINS=https://<your-vercel-app>.vercel.app
```

Redeploy the Render backend, then test:

- Frontend: `https://<your-vercel-app>.vercel.app`
- Backend health: `https://<your-render-backend>.onrender.com/api/health`

SQLite on Render without a persistent disk is ephemeral. For durable goals, activity, journal, and snapshots, add a Render persistent disk and point `VAULTBOARD_DB_PATH` to that mounted path, or move persistence to an external database later.

## Deploy on AWS ECS (Fargate)

This repo also includes production Dockerfiles for the FastAPI backend and Next.js frontend, plus a two-container Fargate task template. See `ecs/README.md` for the AWS production path.
