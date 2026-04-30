"""Persist broker connections + sync cursors (local JSON).

This keeps secrets (access tokens) OUT of git and out of Streamlit session state.
For production, move this to a proper datastore + KMS/Secrets Manager.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BROKER_PATH = Path(__file__).resolve().parent / "broker_connections.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
    p = path or DEFAULT_BROKER_PATH
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return [BrokerConnection.from_dict(x) for x in data if isinstance(x, dict)]


def save_connections(rows: list[BrokerConnection], path: Path | None = None) -> None:
    p = path or DEFAULT_BROKER_PATH
    out = [r.to_dict() for r in rows]
    with p.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def upsert_connection(conn: BrokerConnection, *, path: Path | None = None) -> BrokerConnection:
    rows = load_connections(path)
    key = (conn.provider, conn.user_id)
    kept: list[BrokerConnection] = [r for r in rows if (r.provider, r.user_id) != key]
    kept.append(conn)
    save_connections(kept, path)
    return conn


def get_connection(provider: str, user_id: str, *, path: Path | None = None) -> BrokerConnection | None:
    for r in load_connections(path):
        if r.provider == provider and r.user_id == user_id:
            return r
    return None


def mark_sync(conn: BrokerConnection, *, holdings: bool = False, path: Path | None = None) -> BrokerConnection:
    now = _utc_now_iso()
    conn.last_sync_at = now
    if holdings:
        conn.holdings_last_sync_at = now
    return upsert_connection(conn, path=path)

