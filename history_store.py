"""Append and read portfolio value snapshots for historical charts."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from db_store import connect, is_json_path, json_dumps, json_loads_dict, load_json_file, table_is_empty, utc_now_iso

DEFAULT_SNAPSHOTS_PATH = Path(__file__).resolve().parent / "portfolio_snapshots.json"


def load_snapshots(path: Path | None = None) -> list[dict[str, Any]]:
    if is_json_path(path):
        return _load_snapshots_json(Path(path))

    with connect(path) as conn:
        if path is None:
            _migrate_json_snapshots_if_needed(conn)
        rows = conn.execute(
            """
            SELECT date, recorded_at, total_market_value_cad, usd_cad, source,
                   by_account_cad, by_symbol_cad
            FROM snapshots
            ORDER BY date
            """
        ).fetchall()
        return [_snapshot_from_row(r) for r in rows]


def save_snapshots(rows: list[dict[str, Any]], path: Path | None = None) -> None:
    if is_json_path(path):
        _save_snapshots_json(rows, Path(path))
        return

    ordered = sorted(rows or [], key=lambda r: str(r.get("date", "")))
    with connect(path) as conn:
        conn.execute("DELETE FROM snapshots")
        conn.executemany(
            """
            INSERT INTO snapshots (
                date, recorded_at, total_market_value_cad, usd_cad, source,
                by_account_cad, by_symbol_cad
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [_snapshot_params(r) for r in ordered],
        )
        conn.commit()


def _load_snapshots_json(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or DEFAULT_SNAPSHOTS_PATH
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _save_snapshots_json(rows: list[dict[str, Any]], path: Path | None = None) -> None:
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
    key = snapshot_date.isoformat()
    new_row = {
        "date": key,
        "recorded_at": utc_now_iso(),
        "total_market_value_cad": float(total_market_value_cad),
        "usd_cad": float(usd_cad),
        "source": source,
        "by_account_cad": dict(by_account_cad or {}),
        "by_symbol_cad": dict(by_symbol_cad or {}),
    }
    if is_json_path(path):
        rows = load_snapshots(path)
        out = [r for r in rows if str(r.get("date")) != key]
        out.append(new_row)
        save_snapshots(out, path)
        return out

    with connect(path) as conn:
        if path is None:
            _migrate_json_snapshots_if_needed(conn)
        conn.execute(
            """
            INSERT INTO snapshots (
                date, recorded_at, total_market_value_cad, usd_cad, source,
                by_account_cad, by_symbol_cad
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                recorded_at = excluded.recorded_at,
                total_market_value_cad = excluded.total_market_value_cad,
                usd_cad = excluded.usd_cad,
                source = excluded.source,
                by_account_cad = excluded.by_account_cad,
                by_symbol_cad = excluded.by_symbol_cad
            """,
            _snapshot_params(new_row),
        )
        conn.commit()
    return load_snapshots(path)


def snapshots_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["date", "total_market_value_cad", "usd_cad", "source"])
    df = pd.DataFrame(rows)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    return df.sort_values("date") if "date" in df.columns else df


def _snapshot_params(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(row.get("date") or ""),
        str(row.get("recorded_at") or utc_now_iso()),
        float(row.get("total_market_value_cad") or 0.0),
        float(row.get("usd_cad") or 1.0),
        str(row.get("source") or ""),
        json_dumps(row.get("by_account_cad") or {}),
        json_dumps(row.get("by_symbol_cad") or {}),
    )


def _snapshot_from_row(row) -> dict[str, Any]:
    return {
        "date": row["date"],
        "recorded_at": row["recorded_at"],
        "total_market_value_cad": float(row["total_market_value_cad"]),
        "usd_cad": float(row["usd_cad"]),
        "source": row["source"],
        "by_account_cad": json_loads_dict(row["by_account_cad"]),
        "by_symbol_cad": json_loads_dict(row["by_symbol_cad"]),
    }


def _migrate_json_snapshots_if_needed(conn) -> None:
    if not table_is_empty(conn, "snapshots"):
        return
    data = load_json_file(DEFAULT_SNAPSHOTS_PATH)
    if not isinstance(data, list):
        return
    rows = [r for r in data if isinstance(r, dict) and r.get("date")]
    if not rows:
        return
    conn.executemany(
        """
        INSERT OR REPLACE INTO snapshots (
            date, recorded_at, total_market_value_cad, usd_cad, source,
            by_account_cad, by_symbol_cad
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [_snapshot_params(r) for r in rows],
    )
    conn.commit()
