from pathlib import Path

from portfolio_loader import approx_total_market_value_cad, load_holdings_csv, parse_as_of_date


def test_load_holdings_csv_strips_as_of_and_coerces_values(tmp_path: Path) -> None:
    csv_path = tmp_path / "holdings.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Account Name,Symbol,Name,Security Type,Quantity,Market Value,Market Value Currency,Market Unrealized Returns",
                "TFSA,AAPL,Apple Inc,EQUITY,2,100,USD,10",
                "RRSP,VFV,Vanguard ETF,EXCHANGE_TRADED_FUND,3,200,CAD,20",
                "As of 2026-04-18,,,,,,,",
            ]
        ),
        encoding="utf-8",
    )

    df, as_of = load_holdings_csv(csv_path)

    assert as_of == "As of 2026-04-18"
    assert len(df) == 2
    assert df["Quantity"].sum() == 5
    assert df.loc[df["Symbol"] == "AAPL", "mv_ccy"].iloc[0] == "USD"
    assert parse_as_of_date(as_of).date().isoformat() == "2026-04-18"
    assert approx_total_market_value_cad(df, 1.4) == 340.0
