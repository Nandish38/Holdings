# Auth0 in front of Vaultboard (Option 1)

Put **oauth2-proxy** (or any OIDC-capable reverse proxy) **in front of** Streamlit. Users sign in with **Auth0** before they reach the app. Streamlit does not need OAuth code inside `app.py`.

## Architecture

```text
Internet → HTTPS (ALB or host) → oauth2-proxy:4180 → Streamlit:8501 (private)
```

- Only **oauth2-proxy** is exposed.
- **Streamlit** listens on an internal network (Docker network or `127.0.0.1` on the host).

## Auth0 dashboard

1. **Applications** → **Create** → **Regular Web Application** (or **Web**).
2. **Settings**
   - **Allowed Callback URLs**: must include your oauth2-proxy callback, e.g.  
     `https://vaultboard.example.com/oauth2/callback`  
     For local compose: `http://localhost:4180/oauth2/callback`
   - **Allowed Logout URLs**: e.g. `https://vaultboard.example.com/`
   - **Application Login URI** (optional): your app root.
3. Note:
   - **Domain** (Auth0): `https://<tenant>.<region>.auth0.com` (or custom domain)
   - **Client ID** and **Client Secret**

**OIDC issuer URL** for oauth2-proxy is:

`https://<tenant>.<region>.auth0.com/`

(trailing slash often required)

## Cookie secret (oauth2-proxy)

Generate a random 32-byte key, base64-encoded (example):

```bash
# Linux / macOS
openssl rand -base64 32
```

## Local: Docker Compose

From repo root:

```bash
cd deploy/oauth2-proxy
cp .env.example .env
# Edit .env: Auth0 client id/secret, cookie secret, issuer URL
docker compose up --build
```

Open **http://localhost:4180** (not 8501). You should be redirected to Auth0, then to Streamlit.

## AWS ECS (Fargate) — pattern

1. **Task definition** with **two containers** (same task, awsvpc):
   - **streamlit**: image from this repo, port **8501**, **not** in the public target group.
   - **oauth2-proxy**: public image `quay.io/oauth2-proxy/oauth2-proxy`, port **4180** (or **80**), **this** is the target group port for the ALB.
2. **ALB** → target group → container **oauth2-proxy** only.
3. **Environment** for oauth2-proxy: use the same flags as in `docker-compose.yml` (as env vars or command args). Store **client secret** and **cookie secret** in **Secrets Manager** / SSM.
4. **Security group**: only the ALB can reach the task; or keep task private and ALB in public subnets as usual.

**Redirect URL** in Auth0 must match your real HTTPS URL, e.g.  
`https://<your-alb-or-domain>/oauth2/callback`

## App-level password (optional)

If you use this proxy, you usually **remove** `VAULTBOARD_USERNAME` / `VAULTBOARD_PASSWORD` (and `[auth]` in Streamlit secrets) so users are not asked to log in **twice**.

Keep **`?public=1`** only if you still want a separate unauthenticated path (usually you skip this for locked-down ECS deployments).

## References

- [oauth2-proxy](https://oauth2-proxy.github.io/oauth2-proxy/)
- [Auth0 OIDC](https://auth0.com/docs/get-started/apis/openid-connect-profile)
