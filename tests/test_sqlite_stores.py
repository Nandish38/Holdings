import json
from datetime import date
from pathlib import Path

import goals_store
import history_store
from goals_store import PortfolioGoals, load_goals, save_goals
from history_store import load_snapshots, upsert_snapshot


def test_snapshot_upsert_replaces_same_day(tmp_path: Path) -> None:
    db_path = tmp_path / "vaultboard.db"

    upsert_snapshot(date(2026, 1, 1), 100.0, 1.3, "first", path=db_path)
    upsert_snapshot(date(2026, 1, 1), 125.0, 1.4, "replace", path=db_path)

    rows = load_snapshots(db_path)
    assert len(rows) == 1
    assert rows[0]["total_market_value_cad"] == 125.0
    assert rows[0]["source"] == "replace"


def test_goals_round_trip_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "vaultboard.db"
    goals = PortfolioGoals(
        target_portfolio_value_cad=100_000,
        target_annual_return_pct=6,
        months_to_goal=120,
        account_targets_cad={"TFSA": 10_000},
    )

    save_goals(goals, db_path)
    loaded = load_goals(db_path)

    assert loaded.target_portfolio_value_cad == 100_000
    assert loaded.account_targets_cad == {"TFSA": 10_000}


def test_json_goals_and_snapshots_migrate_when_db_is_empty(tmp_path: Path, monkeypatch) -> None:
    goals_json = tmp_path / "portfolio_goals.json"
    goals_json.write_text(
        json.dumps({"target_portfolio_value_cad": 50_000, "account_targets_cad": {"RRSP": 20_000}}),
        encoding="utf-8",
    )
    snapshots_json = tmp_path / "portfolio_snapshots.json"
    snapshots_json.write_text(
        json.dumps(
            [
                {
                    "date": "2026-01-01",
                    "recorded_at": "2026-01-01T00:00:00+00:00",
                    "total_market_value_cad": 100.0,
                    "usd_cad": 1.4,
                    "source": "legacy",
                    "by_account_cad": {"RRSP": 100.0},
                    "by_symbol_cad": {"VFV": 100.0},
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(goals_store, "DEFAULT_GOALS_PATH", goals_json)
    monkeypatch.setattr(history_store, "DEFAULT_SNAPSHOTS_PATH", snapshots_json)

    db_path = tmp_path / "vaultboard.db"
    monkeypatch.setenv("VAULTBOARD_DB_PATH", str(db_path))

    assert load_goals().target_portfolio_value_cad == 50_000
    assert load_snapshots()[0]["by_symbol_cad"] == {"VFV": 100.0}
