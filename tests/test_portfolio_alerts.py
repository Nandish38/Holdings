from datetime import date

import pandas as pd

from goals_store import PortfolioGoals
from portfolio_alerts import core_alerts


def test_core_alerts_detect_stale_data_and_concentration() -> None:
    df = pd.DataFrame(
        [
            {"Symbol": "AAPL", "Market Value": 80.0, "mv_ccy": "CAD"},
            {"Symbol": "VFV", "Market Value": 20.0, "mv_ccy": "CAD"},
        ]
    )
    goals = PortfolioGoals(max_single_position_pct=50.0)

    flags = core_alerts(
        df,
        goals,
        as_of_date=pd.Timestamp("2026-01-01"),
        account_values_cad={},
        today=date(2026, 2, 15),
    )

    titles = [f.title for f in flags]
    assert "Holdings data may be stale" in titles
    assert "Portfolio concentration in AAPL" in titles


def test_core_alerts_detect_currency_exposure_and_account_drift() -> None:
    df = pd.DataFrame(
        [
            {"Symbol": "AAPL", "Market Value": 100.0, "mv_ccy": "USD"},
            {"Symbol": "VFV", "Market Value": 100.0, "mv_ccy": "CAD"},
        ]
    )
    goals = PortfolioGoals(account_targets_cad={"TFSA": 1_000})

    flags = core_alerts(
        df,
        goals,
        as_of_date=pd.Timestamp("2026-02-14"),
        account_values_cad={"TFSA": 500.0},
        usd_cad=1.4,
        today=date(2026, 2, 15),
    )

    titles = [f.title for f in flags]
    assert "High USD exposure" in titles
    assert "Account below target: TFSA" in titles
