"""SQLite persistence helpers for Vaultboard local data."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = APP_ROOT / "vaultboard.db"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_db_path(path: Path | str | None = None) -> Path:
    if path is not None:
        return Path(path)
    env_path = os.getenv("VAULTBOARD_DB_PATH", "").strip()
    return Path(env_path) if env_path else DEFAULT_DB_PATH


def is_json_path(path: Path | str | None) -> bool:
    return path is not None and Path(path).suffix.lower() == ".json"


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    db_path = resolve_db_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            date TEXT PRIMARY KEY,
            recorded_at TEXT NOT NULL,
            total_market_value_cad REAL NOT NULL,
            usd_cad REAL NOT NULL,
            source TEXT NOT NULL,
            by_account_cad TEXT NOT NULL DEFAULT '{}',
            by_symbol_cad TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            when_date TEXT NOT NULL,
            kind TEXT NOT NULL,
            symbol TEXT,
            qty REAL,
            price REAL,
            ccy TEXT,
            text TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            when_date TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            symbol TEXT,
            body TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS broker_connections (
            provider TEXT NOT NULL,
            user_id TEXT NOT NULL,
            item_id TEXT,
            access_token TEXT,
            institution_name TEXT,
            last_sync_at TEXT,
            holdings_last_sync_at TEXT,
            transactions_cursor TEXT,
            PRIMARY KEY (provider, user_id)
        );
        """
    )
    conn.commit()


def table_is_empty(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    return int(row["n"] if row is not None else 0) == 0


def load_json_file(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, sort_keys=True)


def json_loads_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
