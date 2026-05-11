"""Persist a simple activity log (buys/sells/notes) to SQLite."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from db_store import connect, is_json_path, load_json_file, table_is_empty, utc_now_iso


DEFAULT_ACTIVITY_PATH = Path(__file__).resolve().parent / "activity_log.json"


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
        d["created_at"] = d.get("created_at") or utc_now_iso()
        return d


def load_activity(path: Path | None = None) -> list[dict[str, Any]]:
    if is_json_path(path):
        return _load_activity_json(Path(path))

    with connect(path) as conn:
        if path is None:
            _migrate_json_activity_if_needed(conn)
        rows = conn.execute(
            """
            SELECT when_date, kind, symbol, qty, price, ccy, text, created_at
            FROM activity
            ORDER BY when_date DESC, created_at DESC, id DESC
            """
        ).fetchall()
        return [_activity_from_row(r) for r in rows]


def save_activity(rows: list[dict[str, Any]], path: Path | None = None) -> None:
    if is_json_path(path):
        _save_activity_json(rows, Path(path))
        return

    ordered = sorted(rows or [], key=lambda r: (str(r.get("when", "")), str(r.get("created_at", ""))), reverse=True)
    with connect(path) as conn:
        conn.execute("DELETE FROM activity")
        conn.executemany(
            """
            INSERT INTO activity (when_date, kind, symbol, qty, price, ccy, text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [_activity_params(r) for r in ordered],
        )
        conn.commit()


def _load_activity_json(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or DEFAULT_ACTIVITY_PATH
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _save_activity_json(rows: list[dict[str, Any]], path: Path | None = None) -> None:
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
    if is_json_path(path):
        rows = load_activity(path)
        rows.append(item.to_dict())
        save_activity(rows, path)
        return rows

    with connect(path) as conn:
        if path is None:
            _migrate_json_activity_if_needed(conn)
        conn.execute(
            """
            INSERT INTO activity (when_date, kind, symbol, qty, price, ccy, text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _activity_params(item.to_dict()),
        )
        conn.commit()
    return load_activity(path)


def today_iso() -> str:
    return date.today().isoformat()


def _activity_params(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(row.get("when") or today_iso()),
        str(row.get("kind") or "note"),
        row.get("symbol"),
        _float_or_none(row.get("qty")),
        _float_or_none(row.get("price")),
        row.get("ccy"),
        str(row.get("text") or ""),
        str(row.get("created_at") or utc_now_iso()),
    )


def _activity_from_row(row) -> dict[str, Any]:
    return {
        "when": row["when_date"],
        "kind": row["kind"],
        "symbol": row["symbol"],
        "qty": row["qty"],
        "price": row["price"],
        "ccy": row["ccy"],
        "text": row["text"],
        "created_at": row["created_at"],
    }


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _migrate_json_activity_if_needed(conn) -> None:
    if not table_is_empty(conn, "activity"):
        return
    data = load_json_file(DEFAULT_ACTIVITY_PATH)
    if not isinstance(data, list):
        return
    rows = [r for r in data if isinstance(r, dict)]
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO activity (when_date, kind, symbol, qty, price, ccy, text, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [_activity_params(r) for r in rows],
    )
    conn.commit()

