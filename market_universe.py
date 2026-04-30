"""Market universes (S&P 500, TSX Composite) with disk caching.

Notes:
- These universes are large (hundreds of tickers). Pulling momentum + fundamentals for *all*
  symbols can hit rate limits. The app still computes and then displays the top-N ranked rows.
- Constituents change over time; we refresh from public sources and cache to `data/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests


_ROOT = Path(__file__).resolve().parent
_DATA = _ROOT / "data"


@dataclass(frozen=True)
class Universe:
    key: str
    label: str
    symbols: tuple[str, ...]


def _ensure_data_dir() -> None:
    _DATA.mkdir(parents=True, exist_ok=True)


def _download_text(url: str, *, timeout_s: int = 20) -> str:
    r = requests.get(url, timeout=timeout_s, headers={"User-Agent": "holdings-app/1.0"})
    r.raise_for_status()
    return r.text


def _read_html_table(html_text: str) -> pd.DataFrame:
    # Use pure-Python parser stack (html5lib + bs4) to avoid a hard lxml dependency.
    tables = pd.read_html(html_text, flavor="html5lib")
    if not tables:
        return pd.DataFrame()
    # Heuristic: biggest table is usually constituents.
    return max(tables, key=lambda t: int(t.shape[0]) * max(1, int(t.shape[1])))


def _normalize_symbols(syms: pd.Series) -> tuple[str, ...]:
    out: list[str] = []
    for x in syms.dropna().astype(str).tolist():
        t = x.strip().upper()
        if not t:
            continue
        # Yahoo format: BRK.B -> BRK-B
        t = t.replace(".", "-")
        out.append(t)
    # stable unique order
    return tuple(dict.fromkeys(out))


def load_sp500_symbols(*, refresh: bool = False) -> tuple[str, ...]:
    """
    S&P 500 constituents (Yahoo symbols) from Wikipedia.
    """
    _ensure_data_dir()
    cache = _DATA / "universe_sp500.csv"
    if cache.exists() and not refresh:
        df = pd.read_csv(cache)
        if "Symbol" in df.columns:
            syms = _normalize_symbols(df["Symbol"])
            if syms:
                return syms

    html_text = _download_text("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    t = _read_html_table(html_text)
    # Expect a Symbol column
    col = "Symbol" if "Symbol" in t.columns else t.columns[0]
    syms = _normalize_symbols(t[col])
    pd.DataFrame({"Symbol": list(syms)}).to_csv(cache, index=False)
    return syms


def load_tsx_composite_symbols(*, refresh: bool = False) -> tuple[str, ...]:
    """
    TSX Composite constituents from Wikipedia. Symbols are normalized to Yahoo `.TO`.
    """
    _ensure_data_dir()
    cache = _DATA / "universe_tsx_composite.csv"
    if cache.exists() and not refresh:
        df = pd.read_csv(cache)
        if "Symbol" in df.columns:
            syms = _normalize_symbols(df["Symbol"])
            if syms:
                return syms

    html_text = _download_text("https://en.wikipedia.org/wiki/S%26P/TSX_Composite_Index")
    t = _read_html_table(html_text)

    # Wikipedia tables vary; try a few common headings.
    candidate_cols = [
        "Ticker",
        "Symbol",
        "Trading symbol",
        "TSX symbol",
        "Company",
    ]
    col = None
    for c in candidate_cols:
        if c in t.columns:
            col = c
            break
    if col is None:
        col = t.columns[0]

    raw = t[col].dropna().astype(str)
    out: list[str] = []
    for x in raw.tolist():
        s = x.strip().upper()
        if not s:
            continue
        # If row is "Company" column, we can't recover a ticker reliably; skip.
        if " " in s and len(s) > 8:
            continue
        # Normalize: ensure Yahoo TSX suffix.
        if not s.endswith(".TO") and not s.endswith(".V"):
            s = s + ".TO"
        out.append(s.replace(".", "."))
    syms = tuple(dict.fromkeys(out))
    pd.DataFrame({"Symbol": list(syms)}).to_csv(cache, index=False)
    return syms


def get_universes(*, refresh: bool = False) -> list[Universe]:
    sp = load_sp500_symbols(refresh=refresh)
    tx = load_tsx_composite_symbols(refresh=refresh)
    return [
        Universe("curated", "Curated (fast)", ()),
        Universe("sp500", f"S&P 500 ({len(sp)})", sp),
        Universe("tsx", f"TSX Composite ({len(tx)})", tx),
        Universe("both", f"S&P 500 + TSX Composite ({len(sp) + len(tx)})", tuple(dict.fromkeys(list(sp) + list(tx)))),
    ]

