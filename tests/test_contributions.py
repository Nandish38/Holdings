from contributions import monthly_contribution


def test_monthly_contribution_linear_when_return_is_zero() -> None:
    payment, warning = monthly_contribution(
        current_value=1_000,
        target_value=1_600,
        months=6,
        annual_return_pct=0,
    )

    assert payment == 100
    assert warning is None


def test_monthly_contribution_warns_when_goal_already_met() -> None:
    payment, warning = monthly_contribution(
        current_value=2_000,
        target_value=1_000,
        months=12,
        annual_return_pct=5,
    )

    assert payment == 0
    assert warning is not None
