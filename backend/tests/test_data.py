import time

import pandas as pd
import pytest

from core.data import fetch_live_tbill_rate, fetch_prices
from core.errors import DataFetchError, InsufficientDataError, InvalidTickerError
from tests.conftest import make_gbm_prices


def _df(n: int) -> pd.DataFrame:
    return pd.DataFrame({"Close": make_gbm_prices(n)})


def test_empty_raises_invalid_ticker(patch_yf):
    patch_yf(pd.DataFrame())
    with pytest.raises(InvalidTickerError):
        fetch_prices("NOTAREALTICKER")


def test_blank_ticker_raises_invalid_ticker():
    with pytest.raises(InvalidTickerError):
        fetch_prices("   ")


def test_short_history_raises_insufficient(patch_yf):
    patch_yf(_df(30))
    with pytest.raises(InsufficientDataError):
        fetch_prices("AAPL")


def test_network_error_raises_fetch_error(patch_yf):
    patch_yf(pd.DataFrame(), exc=ConnectionError("boom"))
    with pytest.raises(DataFetchError):
        fetch_prices("AAPL")


def test_success_cleans_nans_and_returns_metadata(patch_yf):
    df = _df(100)
    df.iloc[10, 0] = float("nan")
    fake = patch_yf(df, meta={"currency": "INR", "longName": "Reliance Industries Limited"})
    data = fetch_prices("reliance.ns", lookback="2y")
    assert fake.calls[0]["auto_adjust"] is True
    assert fake.calls[0]["period"] == "2y"
    assert len(data.prices) == 99
    assert not data.prices.isna().any()
    assert data.ticker == "RELIANCE.NS"
    assert data.currency == "INR"
    assert data.long_name == "Reliance Industries Limited"
    assert data.last_date == df.index[-1].date().isoformat()


# --- live ^IRX risk-free rate ------------------------------------------------

def test_live_tbill_rate_parses_percent_quote(patch_yf):
    fake = patch_yf(pd.DataFrame({"Close": [3.61, 3.64, float("nan")]}))
    assert fetch_live_tbill_rate() == pytest.approx(0.0364)
    assert fake.calls[0]["timeout"] > 0


def test_live_tbill_rate_none_on_network_error(patch_yf):
    patch_yf(pd.DataFrame(), exc=ConnectionError("blocked"))
    assert fetch_live_tbill_rate() is None


@pytest.mark.parametrize("df", [pd.DataFrame(), pd.DataFrame({"Close": [float("nan")]}),
                                pd.DataFrame({"Close": [99.0]})])
def test_live_tbill_rate_none_on_empty_or_garbage(patch_yf, df):
    patch_yf(df)
    assert fetch_live_tbill_rate() is None


def test_live_tbill_rate_times_out(monkeypatch):
    import core.data as data_mod

    class Slow:
        def history(self, **kwargs):
            time.sleep(1.0)
            return pd.DataFrame({"Close": [3.6]})

    monkeypatch.setattr(data_mod.yf, "Ticker", lambda symbol: Slow())
    start = time.monotonic()
    assert fetch_live_tbill_rate(timeout=0.05) is None
    assert time.monotonic() - start < 0.5


# --- date-range history (backtests) -------------------------------------------

def test_fetch_price_history_passes_date_range(patch_yf):
    from datetime import date

    from core.data import fetch_price_history

    fake = patch_yf(_df(300), meta={"currency": "USD"})
    data = fetch_price_history(" aapl ", date(2016, 11, 1), "2026-11-07")
    call = fake.calls[0]
    assert call["start"] == "2016-11-01" and call["end"] == "2026-11-07"
    assert "period" not in call and call["auto_adjust"] is True
    assert data.ticker == "AAPL" and len(data.prices) == 300

    fake = patch_yf(_df(300))
    fetch_price_history("AAPL", "2020-01-01")
    assert "end" not in fake.calls[0]


def test_fetch_price_history_errors(patch_yf):
    from core.data import fetch_price_history

    patch_yf(pd.DataFrame())
    with pytest.raises(InvalidTickerError):
        fetch_price_history("NOPE", "2020-01-01")
    patch_yf(pd.DataFrame(), exc=ConnectionError("boom"))
    with pytest.raises(DataFetchError):
        fetch_price_history("AAPL", "2020-01-01")
