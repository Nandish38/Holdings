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
h1, h2, h3 { font-family: 'Syne', sans-serif !important; letter-spacing: 0.03em; font-weight: 600 !important; }
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(1200px 520px at 8% -8%, rgba(138, 92, 246, 0.28), transparent 58%),
    radial-gradient(900px 420px at 92% 4%, rgba(34, 211, 238, 0.10), transparent 52%),
    linear-gradient(168deg, #05040a 0%, #0c0b14 38%, #06070f 100%) !important;
}
[data-testid="stHeader"] { background: rgba(6, 5, 12, 0.65); backdrop-filter: blur(12px); border-bottom: 1px solid rgba(255,255,255,0.06); }
.block-container {
  padding-top: 0.75rem !important;
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
