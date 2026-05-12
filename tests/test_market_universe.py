from pathlib import Path

import pandas as pd

import market_universe
from market_universe import _read_html_table, load_sp500_symbols


def test_read_html_table_treats_html_as_literal_content() -> None:
    html = """
    <html><body>
      <table>
        <tr><th>Symbol</th><th>Name</th></tr>
        <tr><td>AAPL</td><td>Apple</td></tr>
      </table>
    </body></html>
    """

    table = _read_html_table(html)

    assert table["Symbol"].tolist() == ["AAPL"]


def test_load_sp500_symbols_falls_back_when_download_fails(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "data"
    monkeypatch.setattr(market_universe, "_DATA", cache)
    monkeypatch.setattr(market_universe, "_download_text", lambda url: (_ for _ in ()).throw(RuntimeError("offline")))

    syms = load_sp500_symbols(refresh=True)

    assert syms == market_universe.FALLBACK_SP500_SYMBOLS


def test_load_sp500_symbols_uses_cache_before_fallback(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / "data"
    cache_dir.mkdir()
    pd.DataFrame({"Symbol": ["ABC", "DEF"]}).to_csv(cache_dir / "universe_sp500.csv", index=False)
    monkeypatch.setattr(market_universe, "_DATA", cache_dir)
    monkeypatch.setattr(market_universe, "_download_text", lambda url: (_ for _ in ()).throw(RuntimeError("offline")))

    syms = load_sp500_symbols(refresh=True)

    assert syms == ("ABC", "DEF")
