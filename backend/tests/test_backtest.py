"""Core backtest tests: no look-ahead, correct slicing, calibration maths and clear errors.

Prices are synthetic and yfinance is mocked, so no network is used.
"""

from __future__ import annotations

import time
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

import core
from core import PriceData, estimate_parameters
from core.backtest import (
    MAX_WINDOWS,
    BacktestDateError,
    history_start,
    rolling_backtest_from_prices,
    single_backtest_from_prices,
    valid_start_range,
)
from core.errors import InsufficientDataError


def gbm_data(n_days=2520, mu=0.10, sigma=0.25, seed=0, end="2026-11-06", tz=None,
             currency="USD", ticker="TEST") -> PriceData:
    rng = np.random.default_rng(seed)
    dt = 1 / 252
    inc = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n_days - 1)
    values = 100.0 * np.exp(np.concatenate([[0.0], np.cumsum(inc)]))
    idx = pd.bdate_range(end=end, periods=n_days, tz=tz)
    prices = pd.Series(values, index=idx, name=ticker)
    return PriceData(prices, ticker, currency, "Test Corp", idx[-1].date().isoformat())


@pytest.fixture(scope="module")
def data():
    return gbm_data()


# --- single ------------------------------------------------------------------------------

def test_single_uses_only_prices_up_to_start(data):
    res = single_backtest_from_prices(data, "2024-03-15", "6m", lookback="2y", n_sims=2000)
    bt = res["backtest"]
    start = pd.Timestamp(bt["start_date"])
    assert start <= pd.Timestamp("2024-03-15")

    # Recompute the estimate from the lookback window alone and compare.
    window = data.prices[(data.prices.index >= start - pd.DateOffset(years=2))
                         & (data.prices.index <= start)]
    expected = estimate_parameters(window.to_numpy())
    assert res["parameters"]["S0"] == pytest.approx(expected.S0, abs=1e-4)
    assert res["parameters"]["sigma"] == pytest.approx(expected.sigma, abs=1e-6)
    assert res["parameters"]["mu"] == pytest.approx(expected.mu, abs=1e-6)
    assert bt["lookback_start_date"] == window.index[0].date().isoformat()


def test_single_estimate_ignores_future_prices(data):
    """Changing every price after the start must not change the forecast at all."""
    start = "2023-06-01"
    base = single_backtest_from_prices(data, start, "3m", n_sims=1000)
    t0 = pd.Timestamp(base["backtest"]["start_date"])
    shocked = data.prices.copy()
    shocked[shocked.index > t0] *= 3.0
    alt = PriceData(shocked, data.ticker, data.currency, data.long_name, data.last_date)
    res = single_backtest_from_prices(alt, start, "3m", n_sims=1000)
    assert res["parameters"] == base["parameters"]
    assert res["analysis"]["final_price"] == base["analysis"]["final_price"]
    assert res["backtest"]["actual_final"] == pytest.approx(base["backtest"]["actual_final"] * 3)


def test_single_actual_path_and_flags(data):
    res = single_backtest_from_prices(data, "2025-05-01", "6m", n_sims=5000)
    bt, fp = res["backtest"], res["analysis"]["final_price"]
    assert len(bt["actual_path"]) == 127
    assert bt["actual_path"][0] == pytest.approx(res["parameters"]["S0"], abs=1e-4)
    assert bt["actual_path"][-1] == bt["actual_final"]
    assert bt["inside_90"] == (fp["p5"] <= bt["actual_final"] <= fp["p95"])
    assert bt["inside_50"] == (fp["p25"] <= bt["actual_final"] <= fp["p75"])
    assert 0 <= bt["percentile_rank"] <= 100
    # The end date is exactly 126 closes after the start.
    dates = data.prices.index
    i = dates.get_loc(pd.Timestamp(bt["start_date"]))
    assert bt["end_date"] == dates[i + 126].date().isoformat()
    assert res["settings"]["mode"] == "single"
    assert res["settings"]["requested_start_date"] == "2025-05-01"
    assert res["settings"]["rate_note"] is None


def test_single_weekend_start_snaps_to_previous_close(data):
    res = single_backtest_from_prices(data, "2025-05-03", "1m", n_sims=1000)  # a Saturday
    assert res["backtest"]["start_date"] == "2025-05-02"


def test_single_handles_tz_aware_index():
    d = gbm_data(tz="Asia/Kolkata", currency="INR", ticker="TCS.NS")
    res = single_backtest_from_prices(d, "2025-01-10", "1m", n_sims=1000)
    assert res["backtest"]["start_date"] == "2025-01-10"


def test_single_percentile_rank_matches_simulation(data):
    res = single_backtest_from_prices(data, "2022-02-01", "1y", n_sims=4000, seed=7)
    h = core.parse_horizon("1y")
    p = res["parameters"]
    paths = core.simulate_gbm(p["S0"], res["parameters"]["mu"], p["sigma"], h.T, h.n_days,
                              4000, 7)
    rank = (paths[:, -1] < res["backtest"]["actual_final"]).mean() * 100
    assert res["backtest"]["percentile_rank"] == pytest.approx(rank, abs=0.05)


def test_single_too_recent_reports_latest_valid_date(data):
    with pytest.raises(BacktestDateError) as exc:
        single_backtest_from_prices(data, "2026-10-01", "6m")
    latest = data.prices.index[-1 - 126].date().isoformat()
    assert latest in str(exc.value)
    assert "too recent" in str(exc.value)


def test_single_after_last_close_is_rejected(data):
    with pytest.raises(BacktestDateError, match="after the last available close"):
        single_backtest_from_prices(data, "2027-01-04", "1m")


def test_single_not_enough_lookback(data):
    first = data.prices.index[0]
    with pytest.raises(InsufficientDataError, match="earliest start date"):
        single_backtest_from_prices(data, (first + pd.DateOffset(months=6)).date(), "1m",
                                    lookback="2y")
    with pytest.raises(InsufficientDataError):
        single_backtest_from_prices(data, (first - pd.DateOffset(days=10)).date(), "1m")


def test_single_risk_free_uses_default_rate_and_says_so(data, monkeypatch):
    called = []
    monkeypatch.setattr("core.rates.fetch_live_tbill_rate", lambda *a, **k: called.append(1) or 0.09)
    res = single_backtest_from_prices(data, "2024-01-02", "6m", drift="risk_free", n_sims=1000)
    assert not called, "backtests must not use today's live ^IRX quote"
    assert res["parameters"]["mu"] == pytest.approx(0.037)
    assert res["settings"]["rate_source"] == "default for USD"
    assert "every start date" in res["settings"]["rate_note"]
    assert "not fetched" in res["settings"]["rate_note"]
    assert res["parameters"]["mu_historical"] != res["parameters"]["mu"]

    res = single_backtest_from_prices(data, "2024-01-02", "6m", drift="risk_free",
                                      risk_free_rate=0.05, n_sims=1000)
    assert res["parameters"]["mu"] == pytest.approx(0.05)
    assert res["settings"]["rate_source"] == "user override"


def test_single_rejects_bad_inputs(data):
    with pytest.raises(ValueError, match="lookback"):
        single_backtest_from_prices(data, "2024-01-02", "6m", lookback="3y")
    with pytest.raises(ValueError, match="risk_free_rate"):
        single_backtest_from_prices(data, "2024-01-02", "6m", risk_free_rate=0.04)
    with pytest.raises(ValueError):
        single_backtest_from_prices(data, "2024-01-02", "6x")


def test_single_backtest_future_date_rejected_before_fetch(monkeypatch):
    monkeypatch.setattr("core.backtest.fetch_price_history",
                        lambda *a, **k: pytest.fail("should not fetch"))
    with pytest.raises(BacktestDateError, match="future"):
        core.single_backtest("AAPL", date.today() + timedelta(days=3), "1m")


def test_single_backtest_fetches_lookback_before_start(monkeypatch, data):
    seen = {}

    def fake(ticker, start, end=None):
        seen.update(ticker=ticker, start=start)
        return data

    monkeypatch.setattr("core.backtest.fetch_price_history", fake)
    core.single_backtest("TEST", "2024-03-15", "6m", lookback="2y", n_sims=1000)
    assert seen["start"] <= date(2022, 3, 15)


# --- rolling -----------------------------------------------------------------------------

def test_rolling_windows_are_valid_and_evenly_spaced(data):
    res = rolling_backtest_from_prices(data, "6m", lookback="2y", n_windows=40, n_sims=1000)
    w = res["windows"]
    assert len(w) == res["summary"]["n_windows"] == 40
    dates = data.prices.index
    starts = [dates.get_loc(pd.Timestamp(x["start_date"])) for x in w]
    assert starts == sorted(starts) and len(set(starts)) == len(starts)
    gaps = np.diff(starts)
    assert gaps.max() - gaps.min() <= 1
    # Every window has a full lookback before it and a full horizon after it.
    first_ok = dates[0] + pd.DateOffset(years=2) - pd.Timedelta(days=7)
    assert all(dates[i] >= first_ok for i in starts)
    assert starts[-1] + 126 == len(dates) - 1
    for x, i in zip(w, starts):
        assert x["end_date"] == dates[i + 126].date().isoformat()
        assert x["actual_final"] == pytest.approx(data.prices.iloc[i + 126], abs=1e-4)
        assert x["p5"] <= x["p25"] <= x["p50"] <= x["p75"] <= x["p95"]
        assert x["inside_90"] == (x["p5"] <= x["actual_final"] <= x["p95"])
        assert x["inside_50"] == (x["p25"] <= x["actual_final"] <= x["p75"])


def test_rolling_estimates_match_single(data):
    roll = rolling_backtest_from_prices(data, "3m", n_windows=8, n_sims=500)
    for w in roll["windows"][::3]:
        single = single_backtest_from_prices(data, w["start_date"], "3m", n_sims=500)
        assert w["S0"] == pytest.approx(single["parameters"]["S0"], abs=1e-4)
        assert w["sigma"] == pytest.approx(single["parameters"]["sigma"], abs=1e-6)
        assert w["mu"] == pytest.approx(single["parameters"]["mu"], abs=1e-6)


def test_rolling_summary_is_consistent(data):
    res = rolling_backtest_from_prices(data, "6m", n_windows=30, n_sims=1000)
    s, w = res["summary"], res["windows"]
    assert s["coverage_90"] == pytest.approx(np.mean([x["inside_90"] for x in w]), abs=1e-6)
    assert s["coverage_50"] == pytest.approx(np.mean([x["inside_50"] for x in w]), abs=1e-6)
    assert s["mean_percentile_rank"] == pytest.approx(np.mean([x["percentile_rank"] for x in w]),
                                                      abs=0.01)
    assert s["pit_histogram"]["bin_edges"] == [float(e) for e in range(0, 101, 10)]
    assert sum(s["pit_histogram"]["counts"]) == s["n_windows"]
    assert s["below_p5"] + s["above_p95"] == pytest.approx(1 - s["coverage_90"], abs=1e-6)
    assert s["first_start_date"] == w[0]["start_date"]


def test_rolling_is_calibrated_on_true_gbm():
    """On data that really is GBM, coverage should be near the nominal levels.

    Non-overlapping 1m windows across 40 years keep the windows independent.
    """
    d = gbm_data(n_days=252 * 40, mu=0.08, sigma=0.2, seed=3)
    res = rolling_backtest_from_prices(d, "1m", lookback="5y", n_windows=40, n_sims=4000)
    s = res["summary"]
    assert 0.75 <= s["coverage_90"] <= 1.0
    assert 0.3 <= s["coverage_50"] <= 0.7
    assert 35 <= s["mean_percentile_rank"] <= 65


def test_rolling_detects_overconfidence_on_fat_tails():
    """Volatility regimes (calm, then a storm) push realised moves outside the bands."""
    rng = np.random.default_rng(11)
    n = 2520
    vol = np.where((np.arange(n - 1) // 252) % 2 == 0, 0.10, 0.45) / np.sqrt(252)
    r = vol * rng.standard_t(3, n - 1) / np.sqrt(3)
    prices = pd.Series(100 * np.exp(np.concatenate([[0], np.cumsum(r)])),
                       index=pd.bdate_range(end="2026-11-06", periods=n))
    d = PriceData(prices, "FAT", "USD", None, "2026-11-06")
    res = rolling_backtest_from_prices(d, "3m", lookback="6mo", n_windows=40, n_sims=2000)
    assert res["summary"]["coverage_90"] < 0.9


def test_rolling_risk_free(data):
    res = rolling_backtest_from_prices(data, "6m", drift="risk_free", n_windows=10, n_sims=500)
    assert all(w["mu"] == pytest.approx(0.037) for w in res["windows"])
    assert res["settings"]["rate_note"]
    assert res["settings"]["risk_free_rate"] == pytest.approx(0.037)


def test_rolling_is_reproducible_and_seeded(data):
    a = rolling_backtest_from_prices(data, "6m", n_windows=10, n_sims=500, seed=1)
    b = rolling_backtest_from_prices(data, "6m", n_windows=10, n_sims=500, seed=1)
    c = rolling_backtest_from_prices(data, "6m", n_windows=10, n_sims=500, seed=2)
    assert a == b
    assert a["windows"][0]["p50"] != c["windows"][0]["p50"]


def test_rolling_limits(data):
    with pytest.raises(ValueError, match="n_windows"):
        rolling_backtest_from_prices(data, "6m", n_windows=MAX_WINDOWS + 1)
    short = gbm_data(n_days=600)
    with pytest.raises(InsufficientDataError, match="too short"):
        rolling_backtest_from_prices(short, "1y", lookback="2y")
    # Fewer available start dates than requested windows: uses what there is.
    few = gbm_data(n_days=504 + 126 + 20)
    res = rolling_backtest_from_prices(few, "6m", lookback="2y", n_windows=40, n_sims=200)
    assert 5 <= res["summary"]["n_windows"] < 40


def test_rolling_is_fast():
    d = gbm_data(n_days=252 * 12)
    t0 = time.perf_counter()
    rolling_backtest_from_prices(d, "1y", lookback="5y", n_windows=40, n_sims=20_000)
    assert time.perf_counter() - t0 < 2.0


def test_rolling_backtest_fetches_long_history(monkeypatch, data):
    seen = {}

    def fake(ticker, start, end=None):
        seen["start"] = start
        return data

    monkeypatch.setattr("core.backtest.fetch_price_history", fake)
    core.rolling_backtest("TEST", "6m", n_windows=5, n_sims=200)
    assert seen["start"] <= date.today() - timedelta(days=365 * 10)


def test_history_start_grows_for_long_lookback_and_horizon():
    today = date(2026, 11, 7)
    assert (today - history_start("6m", "2y", today)).days >= 3652
    assert (today - history_start("5y", "5y", today)).days >= 13 * 365


def test_valid_start_range(data):
    lo, hi = valid_start_range(data, "6m", "2y")
    assert hi == data.prices.index[-127].date().isoformat()
    assert pd.Timestamp(lo) >= data.prices.index[0] + pd.DateOffset(years=2) - pd.Timedelta(days=7)
    assert valid_start_range(gbm_data(n_days=300), "1y", "2y") is None
