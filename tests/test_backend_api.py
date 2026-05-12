from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

import backend.services as services
import goals_store
import history_store
from backend.main import app
from history_store import upsert_snapshot


def test_health_endpoint() -> None:
    client = TestClient(app)

    resp = client.get("/api/health")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_portfolio_summary_endpoint_uses_sample_data() -> None:
    client = TestClient(app)

    resp = client.get("/api/portfolio/summary")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["positions"] > 0
    assert payload["total_cad"] > 0


def test_returns_endpoint_reads_temp_db(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "vaultboard.db"
    monkeypatch.setenv("VAULTBOARD_DB_PATH", str(db_path))
    monkeypatch.setattr(history_store, "DEFAULT_SNAPSHOTS_PATH", tmp_path / "missing_snapshots.json")
    monkeypatch.setattr(goals_store, "DEFAULT_GOALS_PATH", tmp_path / "missing_goals.json")
    upsert_snapshot(date(2026, 1, 1), 100.0, 1.0, "test")
    upsert_snapshot(date(2026, 2, 1), 125.0, 1.0, "test")

    client = TestClient(app)
    resp = client.get("/api/returns/history")

    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["rows"]) == 2
    assert payload["summary"]["raw_change_cad"] == 25.0


def test_activity_and_journal_write_endpoints_use_store(monkeypatch) -> None:
    activity_rows: list[dict] = []
    journal_rows: list[dict] = []
    monkeypatch.setattr(services, "add_activity", lambda payload: activity_rows + [payload])
    monkeypatch.setattr(services, "add_journal", lambda payload: journal_rows + [payload])
    client = TestClient(app)

    activity_resp = client.post("/api/activity", json={"when": "2026-01-01", "kind": "note", "text": "hello"})
    journal_resp = client.post("/api/journal", json={"when": "2026-01-01", "title": "Thesis"})

    assert activity_resp.status_code == 200
    assert activity_resp.json()[0]["text"] == "hello"
    assert journal_resp.status_code == 200
    assert journal_resp.json()[0]["title"] == "Thesis"
