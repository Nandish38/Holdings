"""SQLite persistence helpers for Vaultboard local data."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)

APP_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = APP_ROOT / "vaultboard.db"

# Schema version — bump this when DDL changes
_SCHEMA_VERSION = 1

# Whitelist of valid table names to prevent SQL injection in table_is_empty()
_VALID_TABLES: frozenset[str] = frozenset(
    {"goals", "snapshots", "activity", "journal", "broker_connections"}
)

_DDL = """
CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    payload     TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    date                    TEXT    PRIMARY KEY,
    recorded_at             TEXT    NOT NULL,
    total_market_value_cad  REAL    NOT NULL,
    usd_cad                 REAL    NOT NULL,
    source                  TEXT    NOT NULL,
    by_account_cad          TEXT    NOT NULL DEFAULT '{}',
    by_symbol_cad           TEXT    NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS activity (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    when_date   TEXT    NOT NULL,
    kind        TEXT    NOT NULL,
    symbol      TEXT,
    qty         REAL,
    price       REAL,
    ccy         TEXT,
    text        TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activity_when ON activity(when_date);

CREATE TABLE IF NOT EXISTS journal (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    when_date   TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    symbol      TEXT,
    body        TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_journal_when ON journal(when_date);

CREATE TABLE IF NOT EXISTS broker_connections (
    provider                TEXT    NOT NULL,
    user_id                 TEXT    NOT NULL,
    item_id                 TEXT,
    access_token            TEXT,   -- WARNING: stored in plaintext; consider OS keychain for production
    institution_name        TEXT,
    last_sync_at            TEXT,
    holdings_last_sync_at   TEXT,
    transactions_cursor     TEXT,
    PRIMARY KEY (provider, user_id)
);
"""


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------


def utc_now_iso() -> str:
    """Return current UTC time as ISO-8601 string (microseconds stripped)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_db_path(path: Path | str | None = None) -> Path:
    """Resolve the DB path from argument → env var → default, in that order."""
    if path is not None:
        return Path(path)
    env_path = os.getenv("VAULTBOARD_DB_PATH", "").strip()
    return Path(env_path) if env_path else DEFAULT_DB_PATH


def is_json_path(path: Path | str | None) -> bool:
    return path is not None and Path(path).suffix.lower() == ".json"


# ---------------------------------------------------------------------------
# Schema management
# ---------------------------------------------------------------------------


def _schema_is_current(conn: sqlite3.Connection) -> bool:
    """Check user_version pragma to avoid re-running DDL on every connect."""
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) >= _SCHEMA_VERSION


def init_schema(conn: sqlite3.Connection) -> None:
    """
    Apply DDL only when the schema version is behind the current target.
    Uses PRAGMA user_version so this is a no-op on already-initialised DBs.
    """
    if _schema_is_current(conn):
        return

    # executescript() issues an implicit COMMIT first, so we use it only here
    # where we own the full transaction lifecycle.
    conn.executescript(_DDL)
    conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
    conn.commit()
    logger.debug("Schema initialised at version %d", _SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """
    Open (and if necessary initialise) a Vaultboard SQLite connection.

    Callers are responsible for closing the connection.  Prefer the
    ``get_connection`` context manager for automatic cleanup.
    """
    db_path = resolve_db_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # WAL mode: allows concurrent readers while a writer is active.
    conn.execute("PRAGMA journal_mode=WAL")
    # Enforce FK constraints (SQLite disables them by default).
    conn.execute("PRAGMA foreign_keys=ON")

    init_schema(conn)
    return conn


@contextmanager
def get_connection(
    path: Path | str | None = None,
) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager that opens a connection and guarantees it is closed.

    Usage::

        with get_connection() as conn:
            conn.execute("SELECT ...")
    """
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def table_is_empty(conn: sqlite3.Connection, table: str) -> bool:
    """
    Return True if *table* contains no rows.

    Raises ``ValueError`` for unknown table names to prevent SQL injection.
    """
    if table not in _VALID_TABLES:
        raise ValueError(
            f"Unknown table {table!r}. Valid tables: {sorted(_VALID_TABLES)}"
        )
    row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()  # noqa: S608
    return int(row["n"] if row is not None else 0) == 0


def load_json_file(path: Path) -> Any:
    """Load a JSON file, returning None if the file does not exist."""
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def json_dumps(value: Any) -> str:
    """
    Serialise *value* to a JSON string.

    Passes ``None`` through as the JSON ``null`` literal rather than silently
    coercing it to ``{}``, which would mask missing data.
    """
    return json.dumps(value, sort_keys=True)


def json_loads_dict(value: str | None) -> dict[str, Any]:
    """
    Deserialise a JSON string to a dict.

    Returns ``{}`` on empty/None input.  Logs a warning and returns ``{}`` on
    parse failure so callers get a safe default without silent data loss.
    """
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        logger.warning("json_loads_dict: failed to parse value – %s", exc)
        return {}
    if not isinstance(data, dict):
        logger.warning(
            "json_loads_dict: expected dict, got %s – returning empty dict",
            type(data).__name__,
        )
        return {}
    return data
