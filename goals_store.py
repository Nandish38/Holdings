"""Persist portfolio goals to a small JSON file next to the app."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_GOALS_PATH = Path(__file__).resolve().parent / "portfolio_goals.json"


@dataclass
class PortfolioGoals:
    """Targets the user can edit in the Goals tab."""

    target_portfolio_value_cad: float | None = None
    target_annual_return_pct: float | None = None
    # Horizon for the monthly contribution calculator (months from today).
    months_to_goal: int | None = None
    max_single_position_pct: float | None = 25.0
    max_equity_non_index_pct: float | None = 15.0
    notes: str = ""

    # Per-account optional targets (keys: account label)
    account_targets_cad: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if d.get("account_targets_cad") is None:
            d["account_targets_cad"] = {}
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PortfolioGoals:
        return cls(
            target_portfolio_value_cad=_f(d.get("target_portfolio_value_cad")),
            target_annual_return_pct=_f(d.get("target_annual_return_pct")),
            months_to_goal=_int(d.get("months_to_goal")),
            max_single_position_pct=_f(d.get("max_single_position_pct")),
            max_equity_non_index_pct=_f(d.get("max_equity_non_index_pct")),
            notes=str(d.get("notes") or ""),
            account_targets_cad=dict(d.get("account_targets_cad") or {}),
        )


def _f(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def load_goals(path: Path | None = None) -> PortfolioGoals:
    p = path or DEFAULT_GOALS_PATH
    if not p.exists():
        return PortfolioGoals()
    with p.open("r", encoding="utf-8") as f:
        return PortfolioGoals.from_dict(json.load(f))


def save_goals(goals: PortfolioGoals, path: Path | None = None) -> None:
    p = path or DEFAULT_GOALS_PATH
    with p.open("w", encoding="utf-8") as f:
        json.dump(goals.to_dict(), f, indent=2)
