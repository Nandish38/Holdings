"""Persist broker connections + sync cursors (local SQLite).

This keeps secrets (access tokens) OUT of git and out of Streamlit session state.
For production, move this to a proper datastore + KMS/Secrets Manager.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from db_store import connect, is_json_path, load_json_file, table_is_empty, utc_now_iso


DEFAULT_BROKER_PATH = Path(__file__).resolve().parent / "broker_connections.json"


@dataclass
class BrokerConnection:
    provider: str  # e.g. "plaid"
    user_id: str
    item_id: str | None = None
    access_token: str | None = None
    institution_name: str | None = None
    last_sync_at: str | None = None
    holdings_last_sync_at: str | None = None
    transactions_cursor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BrokerConnection":
        return cls(
            provider=str(d.get("provider") or ""),
            user_id=str(d.get("user_id") or ""),
            item_id=d.get("item_id"),
            access_token=d.get("access_token"),
            institution_name=d.get("institution_name"),
            last_sync_at=d.get("last_sync_at"),
            holdings_last_sync_at=d.get("holdings_last_sync_at"),
            transactions_cursor=d.get("transactions_cursor"),
        )


def load_connections(path: Path | None = None) -> list[BrokerConnection]:
    if is_json_path(path):
        return _load_connections_json(Path(path))

    with connect(path) as conn:
        if path is None:
            _migrate_json_connections_if_needed(conn)
        rows = conn.execute(
            """
            SELECT provider, user_id, item_id, access_token, institution_name,
                   last_sync_at, holdings_last_sync_at, transactions_cursor
            FROM broker_connections
            ORDER BY provider, user_id
            """
        ).fetchall()
        return [BrokerConnection.from_dict(dict(r)) for r in rows]


def save_connections(rows: list[BrokerConnection], path: Path | None = None) -> None:
    if is_json_path(path):
        _save_connections_json(rows, Path(path))
        return

    with connect(path) as conn:
        conn.execute("DELETE FROM broker_connections")
        conn.executemany(
            """
            INSERT INTO broker_connections (
                provider, user_id, item_id, access_token, institution_name,
                last_sync_at, holdings_last_sync_at, transactions_cursor
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [_connection_params(r) for r in rows],
        )
        conn.commit()


def _load_connections_json(path: Path | None = None) -> list[BrokerConnection]:
    p = path or DEFAULT_BROKER_PATH
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return [BrokerConnection.from_dict(x) for x in data if isinstance(x, dict)]


def _save_connections_json(rows: list[BrokerConnection], path: Path | None = None) -> None:
    p = path or DEFAULT_BROKER_PATH
    out = [r.to_dict() for r in rows]
    with p.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def upsert_connection(conn: BrokerConnection, *, path: Path | None = None) -> BrokerConnection:
    if is_json_path(path):
        rows = load_connections(path)
        key = (conn.provider, conn.user_id)
        kept: list[BrokerConnection] = [r for r in rows if (r.provider, r.user_id) != key]
        kept.append(conn)
        save_connections(kept, path)
        return conn

    with connect(path) as db:
        if path is None:
            _migrate_json_connections_if_needed(db)
        db.execute(
            """
            INSERT INTO broker_connections (
                provider, user_id, item_id, access_token, institution_name,
                last_sync_at, holdings_last_sync_at, transactions_cursor
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, user_id) DO UPDATE SET
                item_id = excluded.item_id,
                access_token = excluded.access_token,
                institution_name = excluded.institution_name,
                last_sync_at = excluded.last_sync_at,
                holdings_last_sync_at = excluded.holdings_last_sync_at,
                transactions_cursor = excluded.transactions_cursor
            """,
            _connection_params(conn),
        )
        db.commit()
    return conn


def get_connection(provider: str, user_id: str, *, path: Path | None = None) -> BrokerConnection | None:
    for r in load_connections(path):
        if r.provider == provider and r.user_id == user_id:
            return r
    return None


def mark_sync(conn: BrokerConnection, *, holdings: bool = False, path: Path | None = None) -> BrokerConnection:
    now = utc_now_iso()
    conn.last_sync_at = now
    if holdings:
        conn.holdings_last_sync_at = now
    return upsert_connection(conn, path=path)


def _connection_params(conn: BrokerConnection) -> tuple[Any, ...]:
    return (
        conn.provider,
        conn.user_id,
        conn.item_id,
        conn.access_token,
        conn.institution_name,
        conn.last_sync_at,
        conn.holdings_last_sync_at,
        conn.transactions_cursor,
    )


def _migrate_json_connections_if_needed(conn) -> None:
    if not table_is_empty(conn, "broker_connections"):
        return
    data = load_json_file(DEFAULT_BROKER_PATH)
    if not isinstance(data, list):
        return
    rows = [BrokerConnection.from_dict(x) for x in data if isinstance(x, dict)]
    if not rows:
        return
    conn.executemany(
        """
        INSERT OR REPLACE INTO broker_connections (
            provider, user_id, item_id, access_token, institution_name,
            last_sync_at, holdings_last_sync_at, transactions_cursor
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [_connection_params(r) for r in rows],
    )
    conn.commit()

