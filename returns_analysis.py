"""Contribution-aware return calculations for snapshot history."""

from __future__ import annotations

from typing import Any

import pandas as pd


FLOW_KINDS = {"deposit": 1.0, "withdrawal": -1.0}


def activity_cash_flows(activity_rows: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in activity_rows or []:
        kind = str(row.get("kind") or "").lower().strip()
        sign = FLOW_KINDS.get(kind)
        if sign is None:
            continue
        amount = _activity_amount(row)
        if amount <= 0:
            continue
        when = pd.to_datetime(row.get("when"), errors="coerce")
        if pd.isna(when):
            continue
        rows.append({"date": when.date(), "net_flow_cad": sign * amount})
    if not rows:
        return pd.DataFrame(columns=["date", "net_flow_cad"])
    df = pd.DataFrame(rows)
    return df.groupby("date", as_index=False)["net_flow_cad"].sum().sort_values("date")


def contribution_adjusted_history(
    snapshots: pd.DataFrame,
    activity_rows: list[dict[str, Any]],
) -> pd.DataFrame:
    if snapshots is None or snapshots.empty or "total_market_value_cad" not in snapshots.columns:
        return pd.DataFrame()

    hx = snapshots.copy()
    hx["date"] = pd.to_datetime(hx["date"], errors="coerce").dt.date
    hx["total_market_value_cad"] = pd.to_numeric(hx["total_market_value_cad"], errors="coerce")
    hx = hx.dropna(subset=["date", "total_market_value_cad"]).sort_values("date")
    if hx.empty:
        return hx

    flows = activity_cash_flows(activity_rows)
    if flows.empty:
        hx["net_flow_cad"] = 0.0
    else:
        hx = hx.merge(flows, on="date", how="left")
        hx["net_flow_cad"] = hx["net_flow_cad"].fillna(0.0)

    first_date = hx["date"].iloc[0]
    hx.loc[hx["date"] <= first_date, "net_flow_cad"] = 0.0
    hx["cumulative_net_contributions"] = hx["net_flow_cad"].cumsum()

    base = float(hx["total_market_value_cad"].iloc[0]) or 1.0
    hx["raw_change_cad"] = hx["total_market_value_cad"] - base
    hx["contribution_adjusted_gain_cad"] = hx["raw_change_cad"] - hx["cumulative_net_contributions"]
    hx["raw_index"] = hx["total_market_value_cad"] / base * 100.0
    hx["contribution_adjusted_index"] = (
        (base + hx["contribution_adjusted_gain_cad"]) / base * 100.0
    )
    return hx


def returns_summary(adjusted: pd.DataFrame) -> dict[str, float]:
    if adjusted is None or adjusted.empty:
        return {
            "raw_change_cad": 0.0,
            "net_contributions_cad": 0.0,
            "contribution_adjusted_gain_cad": 0.0,
        }
    last = adjusted.iloc[-1]
    return {
        "raw_change_cad": float(last.get("raw_change_cad") or 0.0),
        "net_contributions_cad": float(last.get("cumulative_net_contributions") or 0.0),
        "contribution_adjusted_gain_cad": float(last.get("contribution_adjusted_gain_cad") or 0.0),
    }


def _activity_amount(row: dict[str, Any]) -> float:
    qty = _float(row.get("qty"))
    price = _float(row.get("price"))
    if qty is not None and price is not None:
        return abs(qty * price)
    if price is not None:
        return abs(price)
    if qty is not None:
        return abs(qty)
    return 0.0


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
