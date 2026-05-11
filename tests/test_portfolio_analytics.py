from datetime import date

import pandas as pd

from portfolio_analytics import (
    allocation_by_field,
    filter_activity_rows,
    filter_journal_rows,
    latest_labels,
    snapshot_detail_history,
)


def test_allocation_by_field_converts_usd_to_cad() -> None:
    df = pd.DataFrame(
        [
            {"Security Type": "EQUITY", "Market Value": 100.0, "mv_ccy": "USD"},
            {"Security Type": "ETF", "Market Value": 200.0, "mv_ccy": "CAD"},
        ]
    )

    out = allocation_by_field(df, "Security Type", usd_cad=1.5)

    equity = out.loc[out["Security Type"] == "EQUITY"].iloc[0]
    assert equity["market_value_cad"] == 150.0
    assert round(float(out["weight_pct"].sum()), 6) == 100.0


def test_snapshot_detail_history_indexes_each_label() -> None:
    snapshots = pd.DataFrame(
        [
            {"date": "2026-01-01", "by_symbol_cad": {"AAPL": 100.0, "VFV": 50.0}},
            {"date": "2026-02-01", "by_symbol_cad": {"AAPL": 125.0, "VFV": 100.0}},
        ]
    )

    hist = snapshot_detail_history(snapshots, "by_symbol_cad")

    assert latest_labels(hist, limit=1) == ["AAPL"]
    vf_last = hist[(hist["label"] == "VFV") & (hist["date"] == date(2026, 2, 1))].iloc[0]
    assert vf_last["index"] == 200.0


def test_activity_and_journal_filters() -> None:
    activity = [
        {"when": "2026-01-01", "kind": "deposit", "symbol": None, "text": "Cash"},
        {"when": "2026-01-02", "kind": "buy", "symbol": "AAPL", "text": "Starter"},
    ]
    journal = [
        {"when": "2026-01-01", "category": "Macro", "symbol": None, "title": "Rates", "body": "Watch"},
        {"when": "2026-01-03", "category": "Thesis", "symbol": "AAPL", "title": "Apple", "body": "Moat"},
    ]

    assert len(filter_activity_rows(activity, kind="buy", query="aapl")) == 1
    assert len(filter_journal_rows(journal, category="Thesis", start_date=date(2026, 1, 2))) == 1
