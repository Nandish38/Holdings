"""Deterministic portfolio alerts that do not require an LLM."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from ai_flags import Flag
from goals_store import PortfolioGoals


def core_alerts(
    df: pd.DataFrame,
    goals: PortfolioGoals,
    *,
    as_of_date: pd.Timestamp | date | None,
    account_values_cad: dict[str, float] | None = None,
    usd_cad: float = 1.0,
    today: date | None = None,
) -> list[Flag]:
    flags: list[Flag] = []
    flags.extend(stale_data_alert(as_of_date, today=today))
    flags.extend(global_concentration_alerts(df, goals, usd_cad=usd_cad))
    flags.extend(currency_exposure_alerts(df, usd_cad=usd_cad))
    flags.extend(account_target_alerts(goals, account_values_cad or {}))
    return _dedupe(flags)


def stale_data_alert(as_of_date: pd.Timestamp | date | None, *, today: date | None = None) -> list[Flag]:
    if as_of_date is None:
        return [
            Flag(
                severity="info",
                title="Holdings date unavailable",
                detail="The CSV did not include a parseable as-of date, so history freshness cannot be verified.",
                symbols=[],
            )
        ]
    current = today or date.today()
    parsed = as_of_date.date() if isinstance(as_of_date, pd.Timestamp) else as_of_date
    age = (current - parsed).days
    if age <= 7:
        return []
    severity = "alert" if age > 30 else "warn"
    return [
        Flag(
            severity=severity,
            title="Holdings data may be stale",
            detail=f"The current file is {age} days old. Refresh the CSV or broker sync before making decisions.",
            symbols=[],
        )
    ]


def global_concentration_alerts(df: pd.DataFrame, goals: PortfolioGoals, *, usd_cad: float) -> list[Flag]:
    if df is None or df.empty or "Symbol" not in df.columns:
        return []
    max_pct = goals.max_single_position_pct
    if max_pct is None:
        return []
    t = df.copy()
    t["_mv_cad"] = t.apply(lambda r: _mv_cad_row(r, usd_cad), axis=1)
    g = t.groupby("Symbol", dropna=False)["_mv_cad"].sum().reset_index()
    total = float(g["_mv_cad"].sum())
    if total <= 0:
        return []
    out: list[Flag] = []
    for _, row in g.iterrows():
        weight = float(row["_mv_cad"]) / total * 100.0
        if weight > float(max_pct):
            sym = str(row["Symbol"])
            out.append(
                Flag(
                    severity="warn",
                    title=f"Portfolio concentration in {sym}",
                    detail=f"{sym} is about {weight:.1f}% of total portfolio value (goal: max {max_pct:.0f}%).",
                    symbols=[sym],
                )
            )
    return out


def currency_exposure_alerts(df: pd.DataFrame, *, usd_cad: float, threshold_pct: float = 35.0) -> list[Flag]:
    if df is None or df.empty:
        return []
    t = df.copy()
    t["_mv_cad"] = t.apply(lambda r: _mv_cad_row(r, usd_cad), axis=1)
    total = float(t["_mv_cad"].sum())
    if total <= 0:
        return []
    ccy = t.get("mv_ccy", pd.Series(["CAD"] * len(t))).astype(str).str.upper()
    usd_value = float(t.loc[ccy.eq("USD"), "_mv_cad"].sum())
    usd_weight = usd_value / total * 100.0
    if usd_weight <= threshold_pct:
        return []
    return [
        Flag(
            severity="info",
            title="High USD exposure",
            detail=f"USD-denominated holdings are about {usd_weight:.1f}% of portfolio value.",
            symbols=[],
        )
    ]


def account_target_alerts(goals: PortfolioGoals, account_values_cad: dict[str, float]) -> list[Flag]:
    targets = dict(goals.account_targets_cad or {})
    if not targets or not account_values_cad:
        return []
    out: list[Flag] = []
    for label, target in targets.items():
        target_f = _float(target)
        if target_f is None or target_f <= 0:
            continue
        current = float(account_values_cad.get(label, 0.0) or 0.0)
        pct = current / target_f * 100.0
        if pct < 90.0:
            out.append(
                Flag(
                    severity="info",
                    title=f"Account below target: {label}",
                    detail=f"This account is about {pct:.0f}% funded versus its target.",
                    symbols=[],
                )
            )
        elif pct > 110.0:
            out.append(
                Flag(
                    severity="info",
                    title=f"Account above target: {label}",
                    detail=f"This account is about {pct:.0f}% of target; consider whether new contributions should go elsewhere.",
                    symbols=[],
                )
            )
    return out


def _mv_cad_row(row: pd.Series, usd_cad: float) -> float:
    mv = row.get("Market Value")
    if mv is None or pd.isna(mv):
        return 0.0
    ccy = str(row.get("mv_ccy", "CAD")).upper()
    value = float(mv)
    return value * usd_cad if ccy == "USD" else value


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe(flags: list[Flag]) -> list[Flag]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    out: list[Flag] = []
    for flag in flags:
        key = (flag.title, tuple(sorted(flag.symbols)))
        if key in seen:
            continue
        seen.add(key)
        out.append(flag)
    return out
