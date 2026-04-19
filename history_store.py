"""Append and read portfolio value snapshots for historical charts."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_SNAPSHOTS_PATH = Path(__file__).resolve().parent / "portfolio_snapshots.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_snapshots(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or DEFAULT_SNAPSHOTS_PATH
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def save_snapshots(rows: list[dict[str, Any]], path: Path | None = None) -> None:
    p = path or DEFAULT_SNAPSHOTS_PATH
    rows = sorted(rows, key=lambda r: str(r.get("date", "")))
    with p.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def upsert_snapshot(
    snapshot_date: date,
    total_market_value_cad: float,
    usd_cad: float,
    source: str,
    *,
    by_account_cad: dict[str, float] | None = None,
    by_symbol_cad: dict[str, float] | None = None,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Insert or replace the row for snapshot_date (one canonical point per calendar day).
    """
    rows = load_snapshots(path)
    key = snapshot_date.isoformat()
    new_row = {
        "date": key,
        "recorded_at": _utc_now_iso(),
        "total_market_value_cad": float(total_market_value_cad),
        "usd_cad": float(usd_cad),
        "source": source,
        "by_account_cad": dict(by_account_cad or {}),
        "by_symbol_cad": dict(by_symbol_cad or {}),
    }
    out = [r for r in rows if str(r.get("date")) != key]
    out.append(new_row)
    save_snapshots(out, path)
    return out


def snapshots_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["date", "total_market_value_cad", "usd_cad", "source"])
    df = pd.DataFrame(rows)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    return df.sort_values("date") if "date" in df.columns else df
