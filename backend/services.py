"""Backend service functions that adapt existing portfolio logic to JSON APIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from activity_store import ActivityItem, append_activity, load_activity
from ai_flags import heuristic_flags
from goals_store import PortfolioGoals, load_goals, save_goals
from history_store import load_snapshots, snapshots_to_dataframe
from journal_store import JournalEntry, append_entry, load_journal
from market_universe import get_universes
from portfolio_alerts import core_alerts
from portfolio_analytics import allocation_by_field, snapshot_detail_history
from portfolio_loader import approx_total_market_value_cad, load_holdings_csv, parse_as_of_date
from returns_analysis import contribution_adjusted_history, returns_summary


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data" / "holdings-report-2026-04-18.csv"


def load_current_holdings(path: str | Path | None = None) -> tuple[pd.DataFrame, str | None]:
    csv_path = Path(path) if path else DEFAULT_CSV
    return load_holdings_csv(csv_path)


def portfolio_summary(*, usd_cad: float = 1.38, path: str | Path | None = None) -> dict[str, Any]:
    df, as_of = load_current_holdings(path)
    sym = symbol_weight_cad(df, usd_cad)
    top = str(sym.iloc[0]["Symbol"]) if not sym.empty else None
    unrealized = float(df["Market Unrealized Returns"].sum(skipna=True) if "Market Unrealized Returns" in df.columns else 0.0)
    return {
        "as_of": str(parse_as_of_date(as_of).date()) if parse_as_of_date(as_of) is not None else as_of,
        "total_cad": approx_total_market_value_cad(df, usd_cad),
        "positions": int(len(df)),
        "unrealized": unrealized,
        "usd_cad": float(usd_cad),
        "top_position": top,
    }


def holdings_rows(*, usd_cad: float = 1.38, path: str | Path | None = None) -> list[dict[str, Any]]:
    df, _ = load_current_holdings(path)
    out = df.copy()
    out["market_value_cad"] = out.apply(lambda r: mv_cad_row(r, usd_cad), axis=1)
    return frame_records(out)


def allocation_payload(*, usd_cad: float = 1.38, path: str | Path | None = None) -> dict[str, list[dict[str, Any]]]:
    df, _ = load_current_holdings(path)
    return {
        "security_type": frame_records(allocation_by_field(df, "Security Type", usd_cad)),
        "currency": frame_records(allocation_by_field(df, "mv_ccy", usd_cad)),
        "accounts": frame_records(account_market_value_cad(df, usd_cad)),
        "symbols": frame_records(symbol_weight_cad(df, usd_cad)),
    }


def returns_payload() -> dict[str, Any]:
    snapshots = snapshots_to_dataframe(load_snapshots())
    activity = load_activity()
    hx = contribution_adjusted_history(snapshots, activity)
    return {
        "rows": frame_records(hx),
        "account_history": frame_records(snapshot_detail_history(snapshots, "by_account_cad")),
        "symbol_history": frame_records(snapshot_detail_history(snapshots, "by_symbol_cad")),
        "summary": returns_summary(hx),
    }


def universes_payload(*, refresh: bool = False) -> list[dict[str, Any]]:
    return [
        {"key": u.key, "label": u.label, "symbols": list(u.symbols)}
        for u in get_universes(refresh=refresh)
    ]


def activity_rows() -> list[dict[str, Any]]:
    return load_activity()


def add_activity(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return append_activity(ActivityItem(**payload))


def journal_rows() -> list[dict[str, Any]]:
    return load_journal()


def add_journal(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return append_entry(JournalEntry(**payload))


def goals_payload() -> dict[str, Any]:
    return load_goals().to_dict()


def update_goals(payload: dict[str, Any]) -> dict[str, Any]:
    goals = PortfolioGoals.from_dict(payload)
    save_goals(goals)
    return goals.to_dict()


def alerts_payload(*, usd_cad: float = 1.38, path: str | Path | None = None) -> list[dict[str, Any]]:
    df, as_of = load_current_holdings(path)
    goals = load_goals()
    acct = account_market_value_cad(df, usd_cad)
    account_values = {str(r["label"]): float(r["market_value_cad"]) for _, r in acct.iterrows()}
    flags = core_alerts(df, goals, as_of_date=parse_as_of_date(as_of), account_values_cad=account_values, usd_cad=usd_cad)
    flags.extend(heuristic_flags(df, goals))
    seen: set[tuple[str, tuple[str, ...]]] = set()
    out: list[dict[str, Any]] = []
    for flag in flags:
        key = (flag.title, tuple(sorted(flag.symbols)))
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "severity": flag.severity,
                "title": flag.title,
                "detail": flag.detail,
                "symbols": flag.symbols,
            }
        )
    return out


def account_market_value_cad(df: pd.DataFrame, usd_cad: float) -> pd.DataFrame:
    keys = [k for k in ["Account Name", "Account Type", "Account Number"] if k in df.columns]
    if not keys:
        keys = ["Account Name"]
    t = df.copy()
    t["_mv_cad"] = t.apply(lambda r: mv_cad_row(r, usd_cad), axis=1)
    g = t.groupby(keys, dropna=False)["_mv_cad"].sum().reset_index(name="market_value_cad")
    g["label"] = g.apply(
        lambda r: " - ".join(str(r[k]) for k in keys if pd.notna(r[k]) and str(r[k]).strip()),
        axis=1,
    )
    return g.sort_values("market_value_cad", ascending=False)


def symbol_weight_cad(df: pd.DataFrame, usd_cad: float) -> pd.DataFrame:
    t = df.copy()
    t["_mv_cad"] = t.apply(lambda r: mv_cad_row(r, usd_cad), axis=1)
    g = t.groupby("Symbol", dropna=False)["_mv_cad"].sum().reset_index(name="market_value_cad")
    total = float(g["market_value_cad"].sum()) or 1.0
    g["weight_pct"] = g["market_value_cad"] / total * 100.0
    return g.sort_values("market_value_cad", ascending=False)


def mv_cad_row(row: pd.Series, usd_cad: float) -> float:
    mv = row.get("Market Value")
    if mv is None or pd.isna(mv):
        return 0.0
    value = float(mv)
    return value * usd_cad if str(row.get("mv_ccy", "CAD")).upper() == "USD" else value


def frame_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    clean = df.copy()
    for col in clean.columns:
        if pd.api.types.is_datetime64_any_dtype(clean[col]):
            clean[col] = clean[col].astype(str)
    clean = clean.where(pd.notnull(clean), None)
    return clean.to_dict(orient="records")
