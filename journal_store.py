"""Persist journal entries (thesis updates / exit notes / macro) to SQLite."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from db_store import connect, is_json_path, load_json_file, table_is_empty, utc_now_iso


DEFAULT_JOURNAL_PATH = Path(__file__).resolve().parent / "journal_entries.json"


@dataclass(frozen=True)
class JournalEntry:
    when: str  # yyyy-mm-dd
    title: str
    category: str = "Thesis"
    body: str = ""
    symbol: str | None = None
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["created_at"] = d.get("created_at") or utc_now_iso()
        return d


def load_journal(path: Path | None = None) -> list[dict[str, Any]]:
    if is_json_path(path):
        return _load_journal_json(Path(path))

    with connect(path) as conn:
        if path is None:
            _migrate_json_journal_if_needed(conn)
        rows = conn.execute(
            """
            SELECT when_date, title, category, symbol, body, created_at
            FROM journal
            ORDER BY when_date DESC, created_at DESC, id DESC
            """
        ).fetchall()
        return [_journal_from_row(r) for r in rows]


def save_journal(rows: list[dict[str, Any]], path: Path | None = None) -> None:
    if is_json_path(path):
        _save_journal_json(rows, Path(path))
        return

    ordered = sorted(rows or [], key=lambda r: (str(r.get("when", "")), str(r.get("created_at", ""))), reverse=True)
    with connect(path) as conn:
        conn.execute("DELETE FROM journal")
        conn.executemany(
            """
            INSERT INTO journal (when_date, title, category, symbol, body, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [_journal_params(r) for r in ordered],
        )
        conn.commit()


def _load_journal_json(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or DEFAULT_JOURNAL_PATH
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _save_journal_json(rows: list[dict[str, Any]], path: Path | None = None) -> None:
    p = path or DEFAULT_JOURNAL_PATH
    rows = list(rows or [])
    rows = sorted(rows, key=lambda r: (str(r.get("when", "")), str(r.get("created_at", ""))), reverse=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def append_entry(entry: JournalEntry, *, path: Path | None = None) -> list[dict[str, Any]]:
    if is_json_path(path):
        rows = load_journal(path)
        rows.append(entry.to_dict())
        save_journal(rows, path)
        return rows

    with connect(path) as conn:
        if path is None:
            _migrate_json_journal_if_needed(conn)
        conn.execute(
            """
            INSERT INTO journal (when_date, title, category, symbol, body, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            _journal_params(entry.to_dict()),
        )
        conn.commit()
    return load_journal(path)


def today_iso() -> str:
    return date.today().isoformat()


def _journal_params(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(row.get("when") or today_iso()),
        str(row.get("title") or "Untitled"),
        str(row.get("category") or "Thesis"),
        row.get("symbol"),
        str(row.get("body") or ""),
        str(row.get("created_at") or utc_now_iso()),
    )


def _journal_from_row(row) -> dict[str, Any]:
    return {
        "when": row["when_date"],
        "title": row["title"],
        "category": row["category"],
        "symbol": row["symbol"],
        "body": row["body"],
        "created_at": row["created_at"],
    }


def _migrate_json_journal_if_needed(conn) -> None:
    if not table_is_empty(conn, "journal"):
        return
    data = load_json_file(DEFAULT_JOURNAL_PATH)
    if not isinstance(data, list):
        return
    rows = [r for r in data if isinstance(r, dict)]
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO journal (when_date, title, category, symbol, body, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [_journal_params(r) for r in rows],
    )
    conn.commit()

