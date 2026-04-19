"""Load and normalize broker-style holdings CSV exports."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


def _is_as_of_row(row: pd.Series) -> bool:
    first = row.iloc[0] if len(row) else None
    if first is None or (isinstance(first, float) and pd.isna(first)):
        return False
    s = str(first).strip()
    return s.lower().startswith("as of")


def load_holdings_csv(path: str | Path) -> tuple[pd.DataFrame, str | None]:
    """
    Returns (holdings_df, as_of_note).
    Drops footer rows and empty lines.
    """
    path = Path(path)
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)

    mask_footer = raw.apply(_is_as_of_row, axis=1)
    as_of = None
    if mask_footer.any():
        as_of = str(raw.loc[mask_footer, raw.columns[0]].iloc[0]).strip()
        raw = raw.loc[~mask_footer]

    raw = raw.replace("", pd.NA).dropna(how="all")

    required = ["Account Name", "Symbol", "Security Type", "Quantity", "Market Value"]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise ValueError(f"CSV missing columns: {missing}")

    df = raw.dropna(subset=["Symbol"]).copy()

    numeric_cols = [
        "Quantity",
        "Market Price",
        "Book Value (CAD)",
        "Book Value (Market)",
        "Market Value",
        "Market Unrealized Returns",
    ]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "Market Value Currency" in df.columns:
        df["mv_ccy"] = df["Market Value Currency"].astype(str).str.upper()
    else:
        df["mv_ccy"] = "CAD"

    return df, as_of


def aggregate_by_symbol(df: pd.DataFrame) -> pd.DataFrame:
    """Sum quantities and market values in original row currencies (no FX conversion)."""
    g = (
        df.groupby(["Symbol", "mv_ccy"], dropna=False)
        .agg(
            quantity=("Quantity", "sum"),
            market_value=("Market Value", "sum"),
            book_value_cad=("Book Value (CAD)", "sum"),
            unrealized=("Market Unrealized Returns", "sum"),
            name=("Name", "first"),
            security_type=("Security Type", "first"),
        )
        .reset_index()
    )
    return g


def aggregate_by_account(df: pd.DataFrame) -> pd.DataFrame:
    key = ["Account Name", "Account Type", "Account Number"]
    key = [k for k in key if k in df.columns]
    if not key:
        key = ["Account Name"]
    g = (
        df.groupby(key, dropna=False)
        .agg(
            market_value=("Market Value", "sum"),
            book_value_cad=("Book Value (CAD)", "sum"),
            unrealized=("Market Unrealized Returns", "sum"),
        )
        .reset_index()
    )
    return g


def parse_as_of_date(as_of_note: str | None) -> pd.Timestamp | None:
    if not as_of_note:
        return None
    m = re.search(r"(\d{4}-\d{2}-\d{2})", as_of_note)
    if not m:
        return None
    return pd.Timestamp(m.group(1))


def approx_total_market_value_cad(df: pd.DataFrame, usd_cad: float) -> float:
    """Convert USD market values using usd_cad; CAD rows pass through."""
    if df.empty:
        return 0.0
    total = 0.0
    for _, row in df.iterrows():
        mv = row.get("Market Value")
        if mv is None or pd.isna(mv):
            continue
        ccy = str(row.get("mv_ccy", "CAD")).upper()
        v = float(mv)
        if ccy == "USD":
            total += v * usd_cad
        else:
            total += v
    return total


def account_label(row: pd.Series) -> str:
    parts = []
    for k in ("Account Name", "Account Type", "Account Number"):
        if k in row.index and pd.notna(row[k]) and str(row[k]).strip():
            parts.append(str(row[k]).strip())
    return " · ".join(parts) if parts else "Account"
