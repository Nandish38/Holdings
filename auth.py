"""Optional password gate for Vaultboard.

Set credentials via environment variables or Streamlit secrets:

    VAULTBOARD_USERNAME / VAULTBOARD_PASSWORD

Or in `.streamlit/secrets.toml`:

    [auth]
    username = "you"
    password = "your-secret"

If username AND password are unset, the app stays open (no gate).

Public portfolio URLs (?public=1) skip sign-in so shared links keep working.
"""

from __future__ import annotations

import os

import streamlit as st

AUTH_SESSION_KEY = "vb_authenticated"


def _credentials() -> tuple[str, str]:
    u = (os.getenv("VAULTBOARD_USERNAME") or "").strip()
    p = (os.getenv("VAULTBOARD_PASSWORD") or "").strip()
    try:
        sec = getattr(st, "secrets", None)
        if sec is not None:
            auth = sec.get("auth")
            if isinstance(auth, dict):
                u = u or str(auth.get("username") or "").strip()
                p = p or str(auth.get("password") or "").strip()
    except Exception:
        pass
    return u, p


def auth_configured() -> bool:
    u, p = _credentials()
    return bool(u and p)


def is_signed_in() -> bool:
    return bool(st.session_state.get(AUTH_SESSION_KEY, False))


def sign_in(username: str, password: str) -> bool:
    u, p = _credentials()
    ok = username.strip() == u and password == p
    if ok:
        st.session_state[AUTH_SESSION_KEY] = True
    return ok


def sign_out() -> None:
    st.session_state.pop(AUTH_SESSION_KEY, None)


def should_gate(*, public_view: bool) -> bool:
    """True when we must show the Authorization page instead of the app."""
    if public_view:
        return False
    if not auth_configured():
        return False
    return not is_signed_in()


def render_authorization_page() -> None:
    """Full-page sign-in (call after theme CSS)."""
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(
            """
<div class="lk-hero" style="margin-top: 2rem;">
  <div class="lk-hero-kicker">Vaultboard</div>
  <div class="lk-hero-title">Authorization</div>
  <div class="lk-hero-sub">Sign in to access your portfolio. Shared public links use <code>?public=1</code> without sign-in.</div>
</div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("vaultboard_auth"):
            user = st.text_input("Username", autocomplete="username")
            pwd = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            if sign_in(user, pwd):
                st.rerun()
            else:
                st.error("Invalid username or password.")
