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
/* Typography + canvas live in inject_lekha_css(); this layer adds tabs/metrics/sidebar chrome only. */
.stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 6px; }
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
  background: linear-gradient(165deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02));
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 14px;
  padding: 12px 14px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
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
  background: linear-gradient(195deg, rgba(14,12,26,0.97), rgba(8,8,18,0.98)) !important;
  border-right: 1px solid rgba(255,255,255,0.08);
  min-width: 280px !important;
  box-shadow: 4px 0 32px rgba(0,0,0,0.2);
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
  background: linear-gradient(160deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02));
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 16px;
  padding: 14px 16px;
  min-width: 0;
  box-shadow: 0 4px 24px rgba(0,0,0,0.12);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.vb-cal-cell:hover, .vb-idx-cell:hover {
  border-color: rgba(167, 139, 250, 0.22);
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
    Vaultboard shell: premium typography, mesh gradient, glass cards, polished nav.
    """
    st.markdown(
        r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Instrument+Serif:ital@0;1&display=swap');

:root {
  --vb-text: #f1f0ff;
  --vb-text-muted: rgba(241, 240, 255, 0.72);
  --vb-accent: #a78bfa;
  --vb-accent-2: #22d3ee;
  --vb-surface: rgba(255, 255, 255, 0.06);
  --vb-border: rgba(255, 255, 255, 0.10);
  --vb-radius: 16px;
  --vb-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}

html, body, [class*="stApp"] {
  font-family: 'Plus Jakarta Sans', system-ui, sans-serif !important;
  color: var(--vb-text) !important;
  -webkit-font-smoothing: antialiased;
}

h1, h2, h3 {
  font-family: 'Instrument Serif', ui-serif, Georgia, serif !important;
  font-weight: 400 !important;
  letter-spacing: -0.02em;
  line-height: 1.15 !important;
}

[data-testid="stAppViewContainer"] {
  background-color: #06060d !important;
  background-image:
    radial-gradient(ellipse 900px 480px at 15% -5%, rgba(139, 92, 246, 0.35), transparent 55%),
    radial-gradient(ellipse 800px 420px at 95% 15%, rgba(34, 211, 238, 0.12), transparent 50%),
    radial-gradient(ellipse 600px 400px at 50% 100%, rgba(99, 102, 241, 0.08), transparent 45%),
    linear-gradient(180deg, #080712 0%, #0c0b18 45%, #07060f 100%) !important;
  background-attachment: fixed !important;
}

[data-testid="stHeader"] {
  background: linear-gradient(180deg, rgba(8, 7, 18, 0.92), rgba(8, 7, 18, 0.75)) !important;
  backdrop-filter: blur(14px) saturate(1.2);
  border-bottom: 1px solid var(--vb-border);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.25);
}

.block-container {
  padding-top: 1.5rem !important;
  padding-left: clamp(1rem, 3vw, 2rem) !important;
  padding-right: clamp(1rem, 3vw, 2rem) !important;
  max-width: 1280px;
}

/* Hide Streamlit chrome clutter */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* Navigation: segmented control + horizontal radio */
[data-testid="stHorizontalBlock"]:has([data-baseweb="radio"]),
[data-testid="stHorizontalBlock"]:has([role="radiogroup"]) {
  margin-bottom: 0.75rem;
}

[data-baseweb="radio"] label,
[role="radiogroup"] label {
  border-radius: 999px !important;
  border: 1px solid var(--vb-border) !important;
  background: rgba(255, 255, 255, 0.04) !important;
  padding: 0.45rem 1rem !important;
  margin: 0 4px 4px 0 !important;
  transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

[data-baseweb="radio"] label:hover,
[role="radiogroup"] label:hover {
  border-color: rgba(167, 139, 250, 0.45) !important;
  background: rgba(255, 255, 255, 0.07) !important;
}

[data-baseweb="radio"] input:checked + div,
[role="radiogroup"] [data-state="checked"],
[role="radiogroup"] input:checked ~ span {
  border-color: rgba(167, 139, 250, 0.55) !important;
  background: linear-gradient(135deg, rgba(167, 139, 250, 0.28), rgba(34, 211, 238, 0.12)) !important;
  box-shadow: 0 0 0 1px rgba(167, 139, 250, 0.2);
}

/* Primary buttons */
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #7c3aed, #2563eb) !important;
  border: none !important;
  border-radius: 12px !important;
  font-weight: 600 !important;
  box-shadow: 0 4px 14px rgba(124, 58, 237, 0.35);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.stButton > button[kind="primary"]:hover {
  box-shadow: 0 6px 20px rgba(124, 58, 237, 0.45);
  transform: translateY(-1px);
}

/* Inputs & sliders */
[data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea,
.stTextInput input, .stNumberInput input {
  border-radius: 10px !important;
}

.stSlider [data-baseweb="slider"] [role="slider"] {
  background: linear-gradient(90deg, var(--vb-accent), var(--vb-accent-2)) !important;
}

/* Expanders */
.streamlit-expanderHeader {
  border-radius: 12px !important;
  font-weight: 600 !important;
}

/* Dataframes: softer container */
[data-testid="stDataFrame"] {
  border-radius: 12px !important;
  overflow: hidden !important;
  border: 1px solid var(--vb-border) !important;
}

/* Dividers */
hr {
  border: none !important;
  height: 1px !important;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent) !important;
  margin: 1.25rem 0 !important;
}

/* Captions */
[data-testid="stCaptionContainer"] {
  color: var(--vb-text-muted) !important;
}

.lk-hero {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--vb-border);
  background: linear-gradient(145deg, rgba(255,255,255,0.09), rgba(255,255,255,0.02));
  border-radius: 20px;
  padding: clamp(1.25rem, 3vw, 1.75rem);
  margin: 4px 0 18px 0;
  box-shadow: var(--vb-shadow);
}
.lk-hero::before {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse 500px 200px at 80% -20%, rgba(167, 139, 250, 0.25), transparent 60%);
  pointer-events: none;
}
.lk-hero-kicker {
  position: relative;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--vb-accent-2);
  opacity: 0.95;
}
.lk-hero-title {
  position: relative;
  font-family: 'Instrument Serif', ui-serif, serif !important;
  font-size: clamp(1.85rem, 4vw, 2.5rem);
  font-weight: 400 !important;
  margin: 8px 0 6px 0;
  background: linear-gradient(135deg, #fff 0%, #e9e4ff 50%, #c7d2fe 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.lk-hero-sub {
  position: relative;
  color: var(--vb-text-muted);
  font-size: 1.05rem;
  line-height: 1.55;
  margin: 6px 0 0 0;
  max-width: 42rem;
}

.lk-card {
  border: 1px solid var(--vb-border);
  background: linear-gradient(160deg, rgba(255,255,255,0.07), rgba(255,255,255,0.02));
  border-radius: var(--vb-radius);
  padding: 16px 16px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
}
.lk-card + .lk-card { margin-top: 12px; }
.lk-muted { color: var(--vb-text-muted); }
.lk-mono { font-variant-numeric: tabular-nums; }

.lk-pillrow { display: flex; flex-wrap: wrap; gap: 10px; margin: 8px 0 14px 0; }
.lk-pill {
  border: 1px solid var(--vb-border);
  background: rgba(255,255,255,0.05);
  backdrop-filter: blur(8px);
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 0.9rem;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  transition: border-color 0.2s ease, transform 0.15s ease;
}
.lk-pill:hover {
  border-color: rgba(167, 139, 250, 0.35);
  transform: translateY(-1px);
}
.lk-pill strong { font-weight: 600; color: #fff; }

.lk-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
  gap: 14px;
  margin-top: 12px;
}
.lk-kpi {
  border: 1px solid var(--vb-border);
  background: rgba(255,255,255,0.04);
  backdrop-filter: blur(10px);
  border-radius: var(--vb-radius);
  padding: 14px 16px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.lk-kpi:hover {
  border-color: rgba(167, 139, 250, 0.25);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.22);
}
.lk-kpi-l { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--vb-text-muted); margin-bottom: 8px; }
.lk-kpi-v { font-size: 1.2rem; font-weight: 700; letter-spacing: -0.02em; }
.lk-kpi-s { font-size: 0.82rem; color: var(--vb-text-muted); margin-top: 8px; }

.lk-chg-pos { color: #4ade80; }
.lk-chg-neg { color: #fb7185; }
.lk-chg-flat { color: #c4b5fd; }
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
