"""North America watchlist (US + TSX): momentum, Yahoo fundamentals, major index strip."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf

# US large-cap / liquid
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
    "PYPL",
)

# TSX: broad ETFs, banks, energy, staples, rails, + common CDR-style tickers (Yahoo .TO / .NE).
TSX_WATCHLIST: tuple[str, ...] = (
    "XIU.TO",
    "XIC.TO",
    "VFV.TO",
    "QQC.TO",
    "ZQQ.TO",
    "HXQ.TO",
    "VGG.TO",
    "XQQ.TO",
    "ZSP.TO",
    "XEG.TO",
    "XGD.TO",
    "XIT.TO",
    "XLY.TO",
    "XFN.TO",
    "XRE.TO",
    "XUT.TO",
    "XST.TO",
    "TD.TO",
    "RY.TO",
    "BMO.TO",
    "BNS.TO",
    "CM.TO",
    "NA.TO",
    "ENB.TO",
    "TRP.TO",
    "CNQ.TO",
    "SU.TO",
    "IMO.TO",
    "ABX.TO",
    "NTR.TO",
    "ATD.TO",
    "L.TO",
    "MRU.TO",
    "DOL.TO",
    "WCN.TO",
    "CP.TO",
    "CNR.TO",
    "WSP.TO",
    "MFC.TO",
    "SLF.TO",
    "GWO.TO",
    "SHOP.TO",
    "LULU.TO",
    "TOU.TO",
    "FTS.TO",
    "EMA.TO",
    "AEM.TO",
    "WPM.TO",
    "FM.TO",
    # CDRs / USD wrappers (symbols vary; Yahoo may omit some)
    "META.TO",
    "GOOG.TO",
    "AMZN.TO",
    "NVDA.TO",
    "AAPL.TO",
    "MSFT.TO",
    "TSLA.TO",
    "NFLX.TO",
    "GOOG.NE",
    "AMZN.NE",
)

DEFAULT_FULL_WATCHLIST: tuple[str, ...] = tuple(dict.fromkeys(list(DEFAULT_US_WATCHLIST) + list(TSX_WATCHLIST)))

MAJOR_INDICES: tuple[tuple[str, str], ...] = (
    ("^GSPC", "S&P 500"),
    ("^IXIC", "Nasdaq"),
    ("^NSEI", "Nifty 50"),
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
        if len(c) < 22:
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
    out: dict[str, Any] = {
        "Symbol": sym,
        "Name": sym,
        "Target": None,
        "Div yield %": None,
        "P/E": None,
    }
    try:
        d = yf.Ticker(sym).info
        out["Name"] = str(d.get("shortName") or d.get("longName") or sym)[:80]
        t = d.get("targetMeanPrice") or d.get("targetMedianPrice")
        if t is not None:
            out["Target"] = float(t)
        dy = d.get("dividendYield")
        if dy is not None and isinstance(dy, (int, float)) and dy == dy:
            out["Div yield %"] = round(float(dy) * 100.0, 2)
        pe = d.get("trailingPE")
        if pe is None or (isinstance(pe, float) and pe != pe):
            pe = d.get("forwardPE")
        if pe is not None and isinstance(pe, (int, float)) and pe == pe:
            out["P/E"] = round(float(pe), 2)
    except Exception:
        pass
    return out


def build_us_watch_table(
    *,
    tickers: tuple[str, ...] | list[str] | None = None,
    sort_by: str = "1M %",
    top_n: int = 25,
    max_workers: int = 16,
) -> pd.DataFrame:
    syms = list(tickers) if tickers else list(DEFAULT_FULL_WATCHLIST)
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
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(df)))) as ex:
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
    for col in ("1M %", "3M %", "Implied upside %", "Div yield %", "P/E"):
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").round(2)
    merged["Last"] = merged["Last"].round(2)
    merged["Analyst target"] = merged["Analyst target"].round(2)
    cols = [
        c
        for c in (
            "Symbol",
            "Name",
            "Last",
            "1M %",
            "3M %",
            "Div yield %",
            "P/E",
            "Analyst target",
            "Implied upside %",
        )
        if c in merged.columns
    ]
    return merged[cols]


def _one_index(sym: str, label: str) -> dict[str, Any]:
    """Last print vs prior *session* daily close; 5m when Yahoo serves it, else daily close."""
    row: dict[str, Any] = {
        "symbol": sym,
        "label": label,
        "last": None,
        "prev_close": None,
        "day_chg_pct": None,
        "ccy": "",
    }
    try:
        t = yf.Ticker(sym)
        d = t.history(period="1mo", interval="1d", auto_adjust=True)
        if d is None or d.empty or "Close" not in d.columns:
            return row
        closes = d["Close"].dropna()
        if len(closes) < 1:
            return row
        prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else float(closes.iloc[-1])
        last_daily = float(closes.iloc[-1])
        intra = t.history(period="5d", interval="5m", auto_adjust=True)
        if intra is not None and not intra.empty and "Close" in intra.columns:
            ic = intra["Close"].dropna()
            last = float(ic.iloc[-1]) if len(ic) else last_daily
        else:
            intra_1h = t.history(period="7d", interval="1h", auto_adjust=True)
            if intra_1h is not None and not intra_1h.empty and "Close" in intra_1h.columns:
                hc = intra_1h["Close"].dropna()
                last = float(hc.iloc[-1]) if len(hc) else last_daily
            else:
                last = last_daily
        row["last"] = last
        row["prev_close"] = prev_close
        row["day_chg_pct"] = (last / prev_close - 1.0) * 100.0 if prev_close else None
        fi = getattr(t, "fast_info", None)
        if fi and hasattr(fi, "get"):
            row["ccy"] = str(fi.get("currency", "") or "")
        else:
            row["ccy"] = "INR" if "NSEI" in sym else "USD"
    except Exception:
        pass
    return row


def fetch_major_indices() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sym, lab in MAJOR_INDICES:
        out.append(_one_index(sym, lab))
    return out


def index_strip_updated_at() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
