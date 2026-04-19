"""Monthly contribution needed to reach a portfolio value goal (lump-sum + growth)."""


def monthly_contribution(
    *,
    current_value: float,
    target_value: float,
    months: int,
    annual_return_pct: float | None,
) -> tuple[float, str | None]:
    """
    Future value with monthly payment C at end of each month:
      FV = PV*(1+rm)^n + C * (((1+rm)^n - 1) / rm)
    Solve for C. If annual_return_pct is None or 0, uses linear savings (no growth on PV or payments).
    Returns (payment, warning_message_or_none).
    """
    if months <= 0:
        return 0.0, "Months to goal must be greater than zero."
    if target_value <= current_value:
        return 0.0, (
            "Current portfolio (CAD approx) is already at or above this target, "
            "so the modeled monthly contribution is $0."
        )

    pv = float(current_value)
    fv = float(target_value)
    n = int(months)
    r_annual = (annual_return_pct or 0.0) / 100.0
    rm = r_annual / 12.0

    if abs(rm) < 1e-12:
        return (fv - pv) / n, None

    growth = (1.0 + rm) ** n
    from_pv = pv * growth
    need = fv - from_pv
    denom = (growth - 1.0) / rm
    if denom <= 0:
        return 0.0, "Could not compute payment (check return assumptions)."

    c = need / denom
    if c < 0:
        return 0.0, (
            "With this expected return, your current balance may reach the goal without "
            "additional contributions (or the goal date is far enough out). "
            "Try a lower expected return or a shorter horizon to size contributions."
        )
    return c, None
