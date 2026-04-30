"""Premium shell CSS + balance privacy helpers for the Streamlit app."""

from __future__ import annotations

import pandas as pd
import streamlit as st

REVEAL_KEY = "reveal_balances"


def reveal_balances() -> bool:
    return bool(st.session_state.get(REVEAL_KEY, False))


def inject_vault_css() -> None:
    st.markdown(
        r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600&family=Syne:wght@500;700&display=swap');
html, body, [class*="stApp"] { font-family: 'Sora', system-ui, sans-serif !important; color: #e8e6f2; }
h1, h2, h3 {
  font-family: 'Syne', sans-serif !important;
  letter-spacing: 0.03em;
  font-weight: 600 !important;
  line-height: 1.28 !important;
  padding-top: 0.12em !important;
  padding-bottom: 0.06em !important;
}
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(1200px 520px at 8% -8%, rgba(138, 92, 246, 0.28), transparent 58%),
    radial-gradient(900px 420px at 92% 4%, rgba(34, 211, 238, 0.10), transparent 52%),
    linear-gradient(168deg, #05040a 0%, #0c0b14 38%, #06070f 100%) !important;
}
[data-testid="stHeader"] { background: rgba(6, 5, 12, 0.65); backdrop-filter: blur(12px); border-bottom: 1px solid rgba(255,255,255,0.06); }
.block-container {
  /* Enough air so the first H2 isn’t clipped under the Streamlit chrome / Syne ascenders */
  padding-top: 1.75rem !important;
  padding-left: 2rem !important;
  padding-right: 2rem !important;
  max-width: 1400px;
}
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid rgba(255,255,255,0.07); padding-bottom: 4px; }
.stTabs [data-baseweb="tab"] {
  border-radius: 999px !important;
  border: 1px solid rgba(255,255,255,0.08) !important;
  background: rgba(255,255,255,0.03) !important;
  padding: 0.35rem 0.9rem !important;
}
.stTabs [aria-selected="true"] {
  background: linear-gradient(120deg, rgba(167,139,250,0.35), rgba(34,211,238,0.15)) !important;
  border-color: rgba(167,139,250,0.45) !important;
}
/* Metrics: prevent Streamlit’s default ellipsis / clipping in tight columns */
[data-testid="stMetric"] {
  background: linear-gradient(160deg, rgba(255,255,255,0.05), rgba(255,255,255,0.015));
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 14px;
  padding: 12px 14px;
  overflow: visible !important;
  min-width: 0;
}
[data-testid="stMetric"] * {
  overflow: visible !important;
  text-overflow: clip !important;
}
[data-testid="stMetric"] label,
[data-testid="stMetric"] [data-testid="stMetricLabel"] {
  white-space: normal !important;
  word-wrap: break-word !important;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
  font-variant-numeric: tabular-nums;
  white-space: normal !important;
  word-break: break-word !important;
  overflow: visible !important;
  text-overflow: clip !important;
  font-size: clamp(0.82rem, 1.6vw, 1.05rem) !important;
  line-height: 1.35 !important;
}
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(12,10,22,0.98), rgba(8,8,14,0.98)) !important;
  border-right: 1px solid rgba(255,255,255,0.06);
  min-width: 280px !important;
}
/* Long paths: scroll instead of mid-word ellipsis */
[data-testid="stSidebar"] input[type="text"] {
  text-overflow: clip !important;
  overflow-x: auto !important;
  white-space: nowrap !important;
}
/*
 * Never set overflow-x: auto on the main block root: per CSS, non-visible overflow-x
 * forces overflow-y to compute to auto and clips the TOP of the first heading (Vaultboard).
 */
section.main [data-testid="stMainBlockContainer"] {
  overflow-x: visible !important;
  overflow-y: visible !important;
}
section.main [data-testid="column"] {
  overflow: visible !important;
}
section.main [data-testid="stMarkdownContainer"] {
  overflow: visible !important;
}
/* Custom header grids (replace st.metric for dates / indices — no ellipsis) */
.vb-cal-grid, .vb-idx-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
  gap: 12px;
  margin: 0 0 10px 0;
}
.vb-cal-cell, .vb-idx-cell {
  background: linear-gradient(160deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px;
  padding: 12px 14px;
  min-width: 0;
}
.vb-cal-l, .vb-idx-name {
  font-size: 0.78rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  opacity: 0.72;
  margin-bottom: 6px;
  white-space: normal;
  word-break: break-word;
}
.vb-cal-v {
  font-size: 1.05rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  white-space: normal;
  word-break: break-word;
  line-height: 1.35;
}
.vb-idx-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 12px;
}
.vb-idx-last {
  font-size: 1.12rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.vb-idx-chg { font-size: 0.92rem; font-variant-numeric: tabular-nums; opacity: 0.9; }
.vb-idx-chg.pos { color: #6ee7b7; }
.vb-idx-chg.neg { color: #fca5a5; }
.vb-idx-chg.flat { color: #c4b5fd; }
.vb-idx-prev {
  margin-top: 8px;
  font-size: 0.82rem;
  opacity: 0.75;
  font-variant-numeric: tabular-nums;
  white-space: normal;
  word-break: break-word;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def inject_lekha_css() -> None:
    """
    A cleaner "public journal" skin inspired by Lekha:
    - simple hero, pill nav, crisp cards
    - readable typography, subtle borders, minimal chrome
    """
    st.markdown(
        r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Fraunces:opsz,wght@9..144,600;700&display=swap');

html, body, [class*="stApp"] { font-family: 'Inter', system-ui, sans-serif !important; color: #eef2ff; }
h1, h2, h3 {
  font-family: 'Fraunces', ui-serif, Georgia, serif !important;
  font-weight: 700 !important;
  letter-spacing: 0.01em;
  line-height: 1.18 !important;
}

[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(1100px 520px at 12% -10%, rgba(196, 181, 253, 0.24), transparent 60%),
    radial-gradient(900px 460px at 92% 0%, rgba(45, 212, 191, 0.14), transparent 55%),
    linear-gradient(170deg, #05050b 0%, #0a0a14 38%, #050610 100%) !important;
}
[data-testid="stHeader"] { background: rgba(6, 6, 12, 0.55); backdrop-filter: blur(10px); border-bottom: 1px solid rgba(255,255,255,0.06); }
.block-container { padding-top: 1.4rem !important; padding-left: 2rem !important; padding-right: 2rem !important; max-width: 1220px; }

/* Hide Streamlit footer/menu affordances */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

.lk-hero {
  border: 1px solid rgba(255,255,255,0.08);
  background: linear-gradient(140deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
  border-radius: 18px;
  padding: 20px 20px;
  margin: 4px 0 14px 0;
}
.lk-hero-kicker {
  font-size: 0.82rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.74;
}
.lk-hero-title { font-size: 2.15rem; margin: 6px 0 4px 0; }
.lk-hero-sub { opacity: 0.82; font-size: 1.02rem; line-height: 1.5; margin: 6px 0 0 0; }

.lk-card {
  border: 1px solid rgba(255,255,255,0.08);
  background: linear-gradient(160deg, rgba(255,255,255,0.055), rgba(255,255,255,0.02));
  border-radius: 16px;
  padding: 14px 14px;
}
.lk-card + .lk-card { margin-top: 12px; }
.lk-muted { opacity: 0.76; }
.lk-mono { font-variant-numeric: tabular-nums; }

.lk-pillrow { display: flex; flex-wrap: wrap; gap: 8px; margin: 6px 0 12px 0; }
.lk-pill {
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.04);
  border-radius: 999px;
  padding: 7px 10px;
  font-size: 0.92rem;
  opacity: 0.92;
}
.lk-pill strong { font-weight: 600; }

.lk-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
  gap: 12px;
  margin-top: 10px;
}
.lk-kpi {
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03);
  border-radius: 16px;
  padding: 12px 14px;
}
.lk-kpi-l { font-size: 0.78rem; letter-spacing: 0.06em; text-transform: uppercase; opacity: 0.72; margin-bottom: 6px; }
.lk-kpi-v { font-size: 1.12rem; font-weight: 600; }
.lk-kpi-s { font-size: 0.84rem; opacity: 0.74; margin-top: 6px; }

.lk-chg-pos { color: #6ee7b7; }
.lk-chg-neg { color: #fca5a5; }
.lk-chg-flat { color: #c4b5fd; }
</style>
        """,
        unsafe_allow_html=True,
    )


def inject_yahoo_css() -> None:
    """A light, market-terminal look (Yahoo Finance-ish)."""
    st.markdown(
        r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

html, body, [class*="stApp"] { font-family: 'Inter', system-ui, sans-serif !important; color: #0f172a; }
h1, h2, h3 { font-family: 'Inter', system-ui, sans-serif !important; font-weight: 650 !important; letter-spacing: -0.01em; }

[data-testid="stAppViewContainer"] { background: #f5f7fb !important; }
[data-testid="stHeader"] { background: rgba(255,255,255,0.85); backdrop-filter: blur(10px); border-bottom: 1px solid rgba(15,23,42,0.08); }
.block-container { padding-top: 1.2rem !important; padding-left: 1.6rem !important; padding-right: 1.6rem !important; max-width: 1240px; }

[data-testid="stSidebar"] { background: #ffffff !important; border-right: 1px solid rgba(15,23,42,0.08); }

/* Cards */
.lk-hero, .lk-card, .lk-kpi, .vb-cal-cell, .vb-idx-cell {
  background: #ffffff !important;
  border: 1px solid rgba(15,23,42,0.10) !important;
  box-shadow: 0 1px 0 rgba(15,23,42,0.03);
}
.lk-hero-title { font-size: 2.0rem; }
.lk-hero-kicker { color: #2563eb; opacity: 1.0; }
.lk-muted { color: rgba(15,23,42,0.70); opacity: 1.0; }
.lk-pill { background: #ffffff; border: 1px solid rgba(15,23,42,0.14); }

/* Market colors */
.lk-chg-pos, .vb-idx-chg.pos { color: #16a34a !important; }
.lk-chg-neg, .vb-idx-chg.neg { color: #dc2626 !important; }
.lk-chg-flat, .vb-idx-chg.flat { color: #2563eb !important; }

/* Make Streamlit metrics look like compact stat tiles */
[data-testid="stMetric"] {
  background: #ffffff;
  border: 1px solid rgba(15,23,42,0.10);
  border-radius: 14px;
  padding: 10px 12px;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def mask_cad(n: float | None, *, reveal: bool, decimals: int = 0) -> str:
    if not reveal:
        return "·······"
    if n is None or (isinstance(n, float) and n != n):
        return "—"
    fmt = f"{{:,.{decimals}f}}"
    return "$" + fmt.format(float(n))


def mask_plain(n: float | None, *, reveal: bool, decimals: int = 0) -> str:
    if not reveal:
        return "·······"
    if n is None or (isinstance(n, float) and n != n):
        return "—"
    return f"{float(n):,.{decimals}f}"


def mask_signed_cad(n: float | None, *, reveal: bool, decimals: int = 0) -> str:
    if not reveal:
        return "·······"
    if n is None or (isinstance(n, float) and n != n):
        return "—"
    v = float(n)
    sign = "+" if v > 0 else ""
    return sign + f"${abs(v):,.{decimals}f}"


def holdings_table_for_display(df: pd.DataFrame, *, reveal: bool) -> pd.DataFrame:
    out = df.copy()
    if reveal:
        return out
    money_cols = [
        c
        for c in (
            "Market Value",
            "Market Price",
            "Book Value (CAD)",
            "Book Value (Market)",
            "Market Unrealized Returns",
        )
        if c in out.columns
    ]
    for c in money_cols:
        out[c] = "·······"
    return out


def watchlist_table_for_display(watch: pd.DataFrame, *, reveal: bool) -> pd.DataFrame:
    if reveal or watch.empty:
        return watch
    out = watch.copy()
    for c in ("Last", "Analyst target", "1M %", "3M %", "Implied upside %", "Div yield %", "P/E"):
        if c in out.columns:
            if c in ("1M %", "3M %", "Implied upside %", "Div yield %", "P/E"):
                continue
            out[c] = "·······"
    return out
