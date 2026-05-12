# Holdings dashboard

Streamlit app for Canadian broker CSV exports: allocation, NYSE+TSX calendar, goal sizing, contribution-adjusted snapshot history, a **US movers** watchlist (Yahoo prices + analyst targets), and optional OpenAI flags.

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Copy `.env.example` to `.env` if you use OpenAI commentary.
If you connect a broker via Plaid, also set `PLAID_CLIENT_ID`, `PLAID_SECRET`, and `PLAID_ENV`.

### Local persistence

Vaultboard stores goals, snapshots, activity, journal entries, and broker sync metadata in a local SQLite database named `vaultboard.db`. Set `VAULTBOARD_DB_PATH` to use another location.

If older JSON files such as `portfolio_goals.json`, `portfolio_snapshots.json`, `activity_log.json`, `journal_entries.json`, or `broker_connections.json` exist, the app migrates them into SQLite the first time the matching table is empty. The JSON files are left in place as a backup.

### Upgrade note

This upgrade adds SQLite-backed app state, contribution-adjusted returns, deterministic portfolio alerts, and focused pytest coverage. Existing JSON state files are migrated automatically on first use.

The dashboard also includes allocation pies for security type and currency, account/symbol history charts from stored snapshots, and filters for Activity and Journal.

### Optional sign-in

Set both `VAULTBOARD_USERNAME` and `VAULTBOARD_PASSWORD` (or `[auth]` in `.streamlit/secrets.toml`) to show an **Authorization** page before the app. Public share links with `?public=1` still work without signing in.

## Deploy on Streamlit Community Cloud

1. Push this repository to GitHub (for example `https://github.com/Nandish38/Holdings`).
2. Sign in at [Streamlit Community Cloud](https://share.streamlit.io/) with GitHub.
3. Click **New app** → pick the **Holdings** repository, branch **main**.
4. Set **Main file path** to `app.py` (repo root).
5. **Advanced settings** → **Python version** 3.12 (or the version shown in Cloud) if the default build fails.
6. Under **Secrets**, paste (adjust as needed):

   ```toml
   OPENAI_API_KEY = "sk-..."
   OPENAI_MODEL = "gpt-4o-mini"
   ```

   Leave secrets empty if you only use rule-based flags.

7. Deploy. Cloud will install `requirements.txt` and run `streamlit run app.py`.

**Note:** `vaultboard.db` is created at runtime on Cloud; it can reset when the app sleeps unless you add external storage later.

## Data

Place a holdings CSV path in the sidebar or upload a file. A small sample lives in `data/holdings-report-2026-04-18.csv`.

## Health checks and alerts

GitHub Actions runs `.github/workflows/app-health.yml` on pushes, pull requests, manual dispatch, and every 6 hours. It installs dependencies, runs `pytest`, compiles core modules, and imports production modules. Enable GitHub email notifications for failed Actions runs to receive alerts when the app health check fails.

## Deploy on AWS ECS (Fargate)

This repo includes a `Dockerfile` and an ECS guide at `ecs/README.md`.

### Auth0 in front of the app (Option 1)

Use **oauth2-proxy** so Auth0 handles login before traffic reaches Streamlit. See **`deploy/oauth2-proxy/README.md`** and **`deploy/oauth2-proxy/docker-compose.yml`** for a local stack and ECS-oriented notes.
