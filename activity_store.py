"""Persist a simple activity log (buys/sells/notes) to JSON."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ACTIVITY_PATH = Path(__file__).resolve().parent / "activity_log.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class ActivityItem:
    when: str  # yyyy-mm-dd
    kind: str  # buy|sell|note|dividend|deposit|withdrawal|rebalance|other
    symbol: str | None = None
    qty: float | None = None
    price: float | None = None
    ccy: str | None = None
    text: str = ""
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["created_at"] = d.get("created_at") or _utc_now_iso()
        return d


def load_activity(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or DEFAULT_ACTIVITY_PATH
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def save_activity(rows: list[dict[str, Any]], path: Path | None = None) -> None:
    p = path or DEFAULT_ACTIVITY_PATH
    rows = list(rows or [])
    rows = sorted(rows, key=lambda r: (str(r.get("when", "")), str(r.get("created_at", ""))), reverse=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def append_activity(
    item: ActivityItem,
    *,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    rows = load_activity(path)
    rows.append(item.to_dict())
    save_activity(rows, path)
    return rows


def today_iso() -> str:
    return date.today().isoformat()

