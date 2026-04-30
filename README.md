# Holdings dashboard

Streamlit app for Canadian broker CSV exports: allocation, NYSE+TSX calendar, goal sizing, snapshot history, a **US movers** watchlist (Yahoo prices + analyst targets), and optional OpenAI flags.

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

**Note:** `portfolio_goals.json` and `portfolio_snapshots.json` are created at runtime on Cloud; they reset when the app sleeps unless you add external storage later.

## Data

Place a holdings CSV path in the sidebar or upload a file. A small sample lives in `data/holdings-report-2026-04-18.csv`.

## Deploy on AWS ECS (Fargate)

This repo includes a `Dockerfile` and an ECS guide at `ecs/README.md`.

### Auth0 in front of the app (Option 1)

Use **oauth2-proxy** so Auth0 handles login before traffic reaches Streamlit. See **`deploy/oauth2-proxy/README.md`** and **`deploy/oauth2-proxy/docker-compose.yml`** for a local stack and ECS-oriented notes.
