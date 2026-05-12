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

## Deploy on AWS ECS (Fargate)

This repo includes production Dockerfiles for the FastAPI backend and Next.js frontend, plus a two-container Fargate task template. See `ecs/README.md`.
