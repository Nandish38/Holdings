"""Pure portfolio analytics helpers used by the Streamlit views."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd


def allocation_by_field(df: pd.DataFrame, field: str, usd_cad: float) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=[field, "market_value_cad", "weight_pct"])
    if field not in df.columns:
        return pd.DataFrame(columns=[field, "market_value_cad", "weight_pct"])

    t = df.copy()
    t["_mv_cad"] = t.apply(lambda r: _mv_cad_row(r, usd_cad), axis=1)
    t[field] = t[field].fillna("Unknown").astype(str).str.strip().replace("", "Unknown")
    g = t.groupby(field, dropna=False)["_mv_cad"].sum().reset_index(name="market_value_cad")
    g = g[g["market_value_cad"].astype(float) > 0].copy()
    total = float(g["market_value_cad"].sum()) or 1.0
    g["weight_pct"] = g["market_value_cad"] / total * 100.0
    return g.sort_values("market_value_cad", ascending=False)


def snapshot_detail_history(snapshots: pd.DataFrame, detail_col: str) -> pd.DataFrame:
    if snapshots is None or snapshots.empty or detail_col not in snapshots.columns:
        return pd.DataFrame(columns=["date", "label", "market_value_cad", "index"])

    rows: list[dict[str, Any]] = []
    for _, snap in snapshots.iterrows():
        snap_date = pd.to_datetime(snap.get("date"), errors="coerce")
        if pd.isna(snap_date):
            continue
        details = snap.get(detail_col) or {}
        if not isinstance(details, dict):
            continue
        for label, value in details.items():
            amount = _float(value)
            if amount is None:
                continue
            rows.append({"date": snap_date.date(), "label": str(label), "market_value_cad": amount})

    if not rows:
        return pd.DataFrame(columns=["date", "label", "market_value_cad", "index"])

    out = pd.DataFrame(rows).sort_values(["label", "date"])
    first = out.groupby("label")["market_value_cad"].transform("first").replace(0, pd.NA)
    out["index"] = (out["market_value_cad"] / first * 100.0).astype(float)
    return out.sort_values(["date", "label"])


def latest_labels(history: pd.DataFrame, *, limit: int = 8) -> list[str]:
    if history is None or history.empty:
        return []
    last = history.sort_values("date").groupby("label", as_index=False).tail(1)
    last = last.sort_values("market_value_cad", ascending=False)
    return last["label"].astype(str).head(limit).tolist()


def filter_activity_rows(
    rows: list[dict[str, Any]],
    *,
    kind: str | None = None,
    query: str = "",
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows or []
        if _date_in_range(row.get("when"), start_date, end_date)
        and (not kind or str(row.get("kind") or "").lower() == kind.lower())
        and _matches_query(row, query, fields=("symbol", "text", "kind"))
    ]


def filter_journal_rows(
    rows: list[dict[str, Any]],
    *,
    category: str | None = None,
    query: str = "",
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows or []
        if _date_in_range(row.get("when"), start_date, end_date)
        and (not category or str(row.get("category") or "").lower() == category.lower())
        and _matches_query(row, query, fields=("symbol", "title", "body", "category"))
    ]


def _mv_cad_row(row: pd.Series, usd_cad: float) -> float:
    mv = row.get("Market Value")
    if mv is None or pd.isna(mv):
        return 0.0
    ccy = str(row.get("mv_ccy", "CAD")).upper()
    value = float(mv)
    return value * usd_cad if ccy == "USD" else value


def _date_in_range(value: Any, start_date: date | None, end_date: date | None) -> bool:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return False
    current = parsed.date()
    if start_date and current < start_date:
        return False
    if end_date and current > end_date:
        return False
    return True


def _matches_query(row: dict[str, Any], query: str, *, fields: tuple[str, ...]) -> bool:
    q = str(query or "").strip().lower()
    if not q:
        return True
    return any(q in str(row.get(field) or "").lower() for field in fields)


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
