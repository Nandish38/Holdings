import pandas as pd

from returns_analysis import contribution_adjusted_history, returns_summary


def test_contribution_adjusted_history_offsets_external_flows() -> None:
    snapshots = pd.DataFrame(
        [
            {"date": "2026-01-01", "total_market_value_cad": 100.0},
            {"date": "2026-02-01", "total_market_value_cad": 130.0},
            {"date": "2026-03-01", "total_market_value_cad": 120.0},
        ]
    )
    activity = [
        {"when": "2026-02-01", "kind": "deposit", "price": 10.0},
        {"when": "2026-03-01", "kind": "withdrawal", "price": 5.0},
    ]

    adjusted = contribution_adjusted_history(snapshots, activity)
    summary = returns_summary(adjusted)

    assert adjusted["cumulative_net_contributions"].iloc[-1] == 5.0
    assert summary["raw_change_cad"] == 20.0
    assert summary["contribution_adjusted_gain_cad"] == 15.0
