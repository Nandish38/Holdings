"""US-listed liquid names: recent momentum + optional Yahoo analyst mean target (not a forecast)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd
import yfinance as yf

# Large-cap / widely traded US symbols (NASDAQ/NYSE). "Trending" here = top recent % change in this set.
DEFAULT_US_WATCHLIST: tuple[str, ...] = (
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "AVGO",
    "AMD",
    "NFLX",
    "COST",
    "PEP",
    "KO",
    "WMT",
    "JPM",
    "BAC",
    "GS",
    "V",
    "MA",
    "UNH",
    "JNJ",
    "LLY",
    "MRK",
    "ABBV",
    "XOM",
    "CVX",
    "COP",
    "DIS",
    "NKE",
    "MCD",
    "SBUX",
    "HD",
    "LOW",
    "CAT",
    "DE",
    "BA",
    "LMT",
    "RTX",
    "PLTR",
    "COIN",
    "HOOD",
    "SMCI",
    "ARM",
    "CRWD",
    "PANW",
    "NOW",
    "SHOP",
    "SQ",
    "PYPL",
)


def _pct_vs_trading_days_back(close: pd.Series, days_back: int) -> float | None:
    s = close.dropna()
    if len(s) < days_back + 2:
        return None
    last = float(s.iloc[-1])
    prev = float(s.iloc[-1 - days_back])
    if prev <= 0:
        return None
    return (last / prev - 1.0) * 100.0


def _hist_row(sym: str) -> dict[str, Any] | None:
    try:
        h = yf.Ticker(sym).history(period="8mo", auto_adjust=True)
        if h is None or h.empty or "Close" not in h.columns:
            return None
        c = h["Close"].dropna()
        if len(c) < 30:
            return None
        last = float(c.iloc[-1])
        return {
            "Symbol": sym,
            "Last": last,
            "1M %": _pct_vs_trading_days_back(c, 21),
            "3M %": _pct_vs_trading_days_back(c, 63),
        }
    except Exception:
        return None


def _info_row(sym: str) -> dict[str, Any]:
    out: dict[str, Any] = {"Symbol": sym, "Name": sym, "Target": None}
    try:
        d = yf.Ticker(sym).info
        out["Name"] = str(d.get("shortName") or d.get("longName") or sym)[:80]
        t = d.get("targetMeanPrice") or d.get("targetMedianPrice")
        if t is not None:
            out["Target"] = float(t)
    except Exception:
        pass
    return out


def build_us_watch_table(
    *,
    tickers: tuple[str, ...] | list[str] | None = None,
    sort_by: str = "1M %",
    top_n: int = 25,
    max_workers: int = 12,
) -> pd.DataFrame:
    syms = list(tickers) if tickers else list(DEFAULT_US_WATCHLIST)
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_hist_row, s): s for s in syms}
        for fut in as_completed(futs):
            r = fut.result()
            if r:
                rows.append(r)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    sort_col = sort_by if sort_by in df.columns else "1M %"
    df = df.dropna(subset=[sort_col]).sort_values(sort_col, ascending=False).head(int(top_n))

    infos: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(df)))) as ex:
        futs = {ex.submit(_info_row, str(s)): str(s) for s in df["Symbol"].tolist()}
        for fut in as_completed(futs):
            infos.append(fut.result())
    meta = pd.DataFrame(infos).rename(columns={"Target": "Analyst target"})
    merged = df.merge(meta, on="Symbol", how="left")
    merged["Last"] = pd.to_numeric(merged["Last"], errors="coerce")
    merged["Analyst target"] = pd.to_numeric(merged.get("Analyst target"), errors="coerce")
    mask = merged["Analyst target"].notna() & (merged["Last"] > 0)
    merged["Implied upside %"] = None
    merged.loc[mask, "Implied upside %"] = (
        merged.loc[mask, "Analyst target"] / merged.loc[mask, "Last"] - 1.0
    ) * 100.0
    for col in ("1M %", "3M %", "Implied upside %"):
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").round(2)
    merged["Last"] = merged["Last"].round(2)
    merged["Analyst target"] = merged["Analyst target"].round(2)
    cols = [c for c in ("Symbol", "Name", "Last", "1M %", "3M %", "Analyst target", "Implied upside %") if c in merged.columns]
    return merged[cols]
