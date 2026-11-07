"""Backtesting: did the model's forecast range contain what actually happened?

For a past start date t, GBM parameters are estimated ONLY from prices in the lookback window
ending at t (no look-ahead), the horizon is simulated from S(t), and the forecast is compared
with the realised prices after t.

- single_backtest: one start date, the full analysis (bands, paths, histogram) plus the actual
  path, the actual final price's percentile rank and whether it fell inside the 50% / 90% bands.
- rolling_backtest: up to 40 evenly spaced start dates. Reports how often the actual final price
  landed inside the 50% and 90% bands (ideal ~50% / ~90%) and a 10-bin histogram of percentile
  ranks (a PIT / calibration histogram: flat = well calibrated).

Price history is downloaded once (core.data.fetch_price_history) and sliced locally.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from .analyze import analyze
from .data import PriceData, fetch_price_history
from .errors import InsufficientDataError, SimulatorError
from .estimate import estimate_parameters
from .horizon import TRADING_DAYS_PER_YEAR, Horizon, parse_horizon
from .rates import RiskFreeRate, infer_currency, resolve_risk_free_rate
from .simulate import simulate_gbm

LOOKBACK_OFFSETS: dict[str, pd.DateOffset] = {
    "6mo": pd.DateOffset(months=6),
    "1y": pd.DateOffset(years=1),
    "2y": pd.DateOffset(years=2),
    "5y": pd.DateOffset(years=5),
}
LOOKBACK_YEARS = {"6mo": 0.5, "1y": 1.0, "2y": 2.0, "5y": 5.0}

DEFAULT_HISTORY_YEARS = 10
# A lookback counts as "full" if the data starts within this many calendar days of its start
# (weekends and holidays mean the first close can sit a few days after the exact date).
LOOKBACK_TOLERANCE_DAYS = 7
MIN_LOOKBACK_PRICES = 60

MAX_WINDOWS = 40
MIN_WINDOWS = 5
DEFAULT_WINDOWS = 40
DEFAULT_ROLLING_SIMS = 2_000
BAND_PERCENTILES = (5, 25, 50, 75, 95)
PIT_BINS = 10


class BacktestDateError(SimulatorError):
    """The requested start date can't be backtested (in the future or too recent)."""


# --- helpers -----------------------------------------------------------------------------

def _check_inputs(lookback: str, drift: str, risk_free_rate: float | None, n_sims: int) -> None:
    from . import _check_drift  # local import: core/__init__ imports this module

    if lookback not in LOOKBACK_OFFSETS:
        raise ValueError(f"lookback must be one of {', '.join(LOOKBACK_OFFSETS)}, got {lookback!r}")
    if n_sims < 1:
        raise ValueError("n_sims must be >= 1")
    _check_drift(drift, risk_free_rate)  # also validates the rate's range


def _dates(prices: pd.Series) -> pd.DatetimeIndex:
    """Exchange-local calendar dates of the closes (tz dropped without shifting the day)."""
    idx = pd.DatetimeIndex(prices.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return idx.normalize()


def _iso(ts: pd.Timestamp) -> str:
    return pd.Timestamp(ts).date().isoformat()


def history_start(horizon: str, lookback: str, today: date | None = None,
                  years: int = DEFAULT_HISTORY_YEARS) -> date:
    """First date to download: at least `years` back, more if lookback + horizon need it."""
    h = parse_horizon(horizon)
    need = LOOKBACK_YEARS.get(lookback, 2.0) + h.T + 3
    span = max(years, math.ceil(need))
    today = today or date.today()
    return today - timedelta(days=int(round(span * 365.25)) + 7)


def _resolve_rate(data: PriceData, drift: str, override: float | None) -> RiskFreeRate | None:
    """Today's rate for every start date: override, else the per-currency default.

    The live ^IRX quote is deliberately skipped: it is today's rate too, and historical
    T-bill rates are not fetched, so a fixed documented default is more honest.
    """
    if drift != "risk_free":
        return None
    return resolve_risk_free_rate(infer_currency(data.ticker, data.currency), override,
                                  allow_live=False)


def _rate_note(rate: RiskFreeRate | None, currency: str | None) -> str | None:
    if rate is None:
        return None
    pct = f"{rate.rate * 100:.2f}%"
    if rate.source == "user override":
        return (f"Your rate ({pct}) is used as the drift at every start date; historical "
                "T-bill rates are not fetched.")
    return (f"Uses today's {rate.source} ({pct}) as the drift at every start date, not the "
            "T-bill rate at the time; historical rates are not fetched.")


def _earliest_valid_index(dates: pd.DatetimeIndex, lookback: str) -> int:
    """Index of the first close that has a full lookback window before it."""
    first_ok = dates[0] + LOOKBACK_OFFSETS[lookback] - pd.Timedelta(days=LOOKBACK_TOLERANCE_DAYS)
    return int(np.searchsorted(dates.values, np.datetime64(first_ok), side="left"))


def _window_start_indices(dates: pd.DatetimeIndex, idx: np.ndarray, lookback: str) -> np.ndarray:
    """For each start index, the first index inside its lookback window (date >= t - lookback)."""
    starts = dates[idx] - LOOKBACK_OFFSETS[lookback]
    return np.searchsorted(dates.values, starts.values, side="left")


def _percentile_rank(sims: np.ndarray, actual: np.ndarray) -> np.ndarray:
    """Percent (0-100) of simulated finals below the actual one, ties counted half (per row)."""
    sims = np.atleast_2d(sims)
    actual = np.asarray(actual, dtype=float).reshape(-1, 1)
    below = (sims < actual).mean(axis=1)
    equal = (sims == actual).mean(axis=1)
    return (below + 0.5 * equal) * 100.0


def _settings(h: Horizon, lookback: str, n_sims: int, seed: int, drift: str,
              rate: RiskFreeRate | None, currency: str | None, mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "horizon": h.label,
        "n_steps": h.n_days,
        "T_years": round(h.T, 6),
        "lookback": lookback,
        "n_sims": int(n_sims),
        "seed": int(seed),
        "trading_days_per_year": TRADING_DAYS_PER_YEAR,
        "drift": drift,
        "risk_free_rate": round(rate.rate, 6) if rate else None,
        "rate_source": rate.source if rate else None,
        "rate_note": _rate_note(rate, currency),
    }


def _metadata(data: PriceData, dates: pd.DatetimeIndex) -> dict[str, Any]:
    return {
        "ticker": data.ticker,
        "currency": data.currency,
        "long_name": data.long_name,
        "first_date": _iso(dates[0]),
        "last_date": _iso(dates[-1]),
        "n_prices": int(len(dates)),
    }


def valid_start_range(data: PriceData, horizon: str, lookback: str) -> tuple[str, str] | None:
    """(earliest, latest) start dates with a full lookback before and full horizon after."""
    dates = _dates(data.prices)
    h = parse_horizon(horizon)
    lo, hi = _earliest_valid_index(dates, lookback), len(dates) - 1 - h.n_days
    if hi < lo or hi < 0:
        return None
    return _iso(dates[lo]), _iso(dates[hi])


# --- single ------------------------------------------------------------------------------

def single_backtest_from_prices(
    data: PriceData,
    start_date: date | str,
    horizon: str,
    lookback: str = "2y",
    drift: str = "historical",
    n_sims: int = 10_000,
    seed: int = 42,
    risk_free_rate: float | None = None,
) -> dict[str, Any]:
    """Backtest one start date on already-fetched prices. Returns a JSON-ready dict."""
    _check_inputs(lookback, drift, risk_free_rate, n_sims)
    h = parse_horizon(horizon)
    prices = data.prices.to_numpy(dtype=float)
    dates = _dates(data.prices)
    requested = pd.Timestamp(start_date).normalize()
    latest_i = len(dates) - 1 - h.n_days
    latest = _iso(dates[latest_i]) if latest_i >= 0 else None

    if requested > dates[-1]:
        raise BacktestDateError(
            f"Start date {_iso(requested)} is after the last available close "
            f"({_iso(dates[-1])}); pick a past date"
            + (f" on or before {latest}" if latest else "") + ".")

    # The start is the last close on or before the requested date: nothing after it is used.
    i = int(np.searchsorted(dates.values, requested.to_datetime64(), side="right")) - 1
    if i < 0:
        raise InsufficientDataError(
            f"No price history on or before {_iso(requested)} (data starts {_iso(dates[0])})")
    if i + h.n_days > len(dates) - 1:
        raise BacktestDateError(
            f"Start date {_iso(requested)} is too recent for a {h.label} horizon: it needs "
            f"{h.n_days} trading days after the start, only {len(dates) - 1 - i} are available. "
            + (f"The latest start date with a full horizon is {latest}." if latest
               else "Pick a shorter horizon."))

    earliest_i = _earliest_valid_index(dates, lookback)
    if i < earliest_i:
        earliest = _iso(dates[earliest_i]) if earliest_i < len(dates) else None
        raise InsufficientDataError(
            f"not enough history before {_iso(dates[i])} for a {lookback} lookback "
            f"(data starts {_iso(dates[0])})"
            + (f"; the earliest start date with a full lookback is {earliest}" if earliest else ""))

    j = int(_window_start_indices(dates, np.array([i]), lookback)[0])
    window = prices[j:i + 1]
    if window.size < MIN_LOOKBACK_PRICES:
        raise InsufficientDataError(
            f"only {window.size} trading days in the lookback before {_iso(dates[i])}; "
            f"need at least {MIN_LOOKBACK_PRICES}")

    params = estimate_parameters(window)
    rate = _resolve_rate(data, drift, risk_free_rate)
    mu = rate.rate if rate else params.mu
    paths = simulate_gbm(params.S0, mu, params.sigma, h.T, h.n_days, n_sims, seed)
    analysis = analyze(paths, params.S0, seed=seed)

    actual_path = prices[i:i + h.n_days + 1]
    actual_final = float(actual_path[-1])
    final = paths[:, -1]
    p5, p25, p75, p95 = np.percentile(final, (5, 25, 75, 95))
    rank = float(_percentile_rank(final, np.array([actual_final]))[0])

    parameters = params.to_dict()
    parameters["mu"] = round(mu, 6)
    parameters["mu_historical"] = round(params.mu, 6)
    settings = _settings(h, lookback, n_sims, seed, drift, rate, data.currency, "single")
    settings["requested_start_date"] = _iso(requested)

    return {
        "metadata": _metadata(data, dates),
        "parameters": parameters,
        "settings": settings,
        "analysis": analysis,
        "backtest": {
            "start_date": _iso(dates[i]),
            "end_date": _iso(dates[i + h.n_days]),
            "lookback_start_date": _iso(dates[j]),
            "latest_start_date": latest,
            "actual_path": [round(float(v), 4) for v in actual_path],
            "actual_final": round(actual_final, 4),
            "actual_return_pct": round((actual_final / params.S0 - 1.0) * 100, 4),
            "percentile_rank": round(rank, 2),
            "inside_50": bool(p25 <= actual_final <= p75),
            "inside_90": bool(p5 <= actual_final <= p95),
        },
    }


def single_backtest(
    ticker: str,
    start_date: date | str,
    horizon: str,
    lookback: str = "2y",
    drift: str = "historical",
    n_sims: int = 10_000,
    seed: int = 42,
    risk_free_rate: float | None = None,
) -> dict[str, Any]:
    """Fetch history once, then backtest one start date. See single_backtest_from_prices."""
    _check_inputs(lookback, drift, risk_free_rate, n_sims)
    start = pd.Timestamp(start_date).date()
    if start > date.today():
        raise BacktestDateError(f"Start date {start.isoformat()} is in the future; pick a past date.")
    # Only the lookback before the start and everything after it are needed.
    first = start - timedelta(days=int(LOOKBACK_YEARS[lookback] * 366) + 14)
    data = fetch_price_history(ticker, first)
    return single_backtest_from_prices(data, start, horizon, lookback=lookback, drift=drift,
                                       n_sims=n_sims, seed=seed, risk_free_rate=risk_free_rate)


# --- rolling -----------------------------------------------------------------------------

def rolling_backtest_from_prices(
    data: PriceData,
    horizon: str,
    lookback: str = "2y",
    drift: str = "historical",
    n_windows: int = DEFAULT_WINDOWS,
    n_sims: int = DEFAULT_ROLLING_SIMS,
    seed: int = 42,
    risk_free_rate: float | None = None,
) -> dict[str, Any]:
    """Evenly spaced past start dates, each with a full lookback before and horizon after.

    Fully vectorised: per-window mu and sigma come from cumulative sums of log returns, and
    final prices are drawn from the exact GBM solution S0 * exp((mu - sigma^2/2) T + sigma
    sqrt(T) Z), the same distribution the daily-step simulator produces at the horizon.
    """
    _check_inputs(lookback, drift, risk_free_rate, n_sims)
    if not 1 <= n_windows <= MAX_WINDOWS:
        raise ValueError(f"n_windows must be between 1 and {MAX_WINDOWS}, got {n_windows}")
    h = parse_horizon(horizon)
    prices = data.prices.to_numpy(dtype=float)
    if np.any(~np.isfinite(prices)) or np.any(prices <= 0):
        raise ValueError("Prices must be finite and strictly positive")
    dates = _dates(data.prices)

    lo = _earliest_valid_index(dates, lookback)
    hi = len(dates) - 1 - h.n_days
    available = hi - lo + 1
    if available < MIN_WINDOWS:
        span = f"{_iso(dates[0])} to {_iso(dates[-1])}"
        raise InsufficientDataError(
            f"history {span} is too short for a {lookback} lookback plus a {h.label} horizon "
            f"(need room for at least {MIN_WINDOWS} start dates). Try a shorter lookback or horizon")
    n = min(n_windows, available)
    idx = np.unique(np.round(np.linspace(lo, hi, n)).astype(int))
    j = _window_start_indices(dates, idx, lookback)

    # Rolling log-return moments over each window [j, i] (returns j..i-1).
    r = np.diff(np.log(prices))
    c1 = np.concatenate([[0.0], np.cumsum(r)])
    c2 = np.concatenate([[0.0], np.cumsum(r * r)])
    m = (idx - j).astype(float)
    if np.any(m + 1 < MIN_LOOKBACK_PRICES):
        raise InsufficientDataError(
            f"some lookback windows have fewer than {MIN_LOOKBACK_PRICES} trading days")
    s1, s2 = c1[idx] - c1[j], c2[idx] - c2[j]
    mean = s1 / m
    var = np.maximum((s2 - m * mean**2) / (m - 1), 0.0)
    sigma = np.sqrt(var * TRADING_DAYS_PER_YEAR)
    mu_hist = mean * TRADING_DAYS_PER_YEAR + 0.5 * sigma**2

    rate = _resolve_rate(data, drift, risk_free_rate)
    mu = np.full_like(mu_hist, rate.rate) if rate else mu_hist

    S0 = prices[idx]
    actual = prices[idx + h.n_days]
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((idx.size, n_sims))
    drift_term = ((mu - 0.5 * sigma**2) * h.T)[:, None]
    finals = S0[:, None] * np.exp(drift_term + (sigma * math.sqrt(h.T))[:, None] * z)

    pct = np.percentile(finals, BAND_PERCENTILES, axis=1)  # (5, n_windows)
    p5, p25, p50, p75, p95 = pct
    ranks = _percentile_rank(finals, actual)
    inside_50 = (actual >= p25) & (actual <= p75)
    inside_90 = (actual >= p5) & (actual <= p95)
    counts, edges = np.histogram(ranks, bins=np.linspace(0, 100, PIT_BINS + 1))

    windows = [
        {
            "start_date": _iso(dates[i]),
            "end_date": _iso(dates[i + h.n_days]),
            "S0": round(float(S0[k]), 4),
            "actual_final": round(float(actual[k]), 4),
            "actual_return_pct": round(float((actual[k] / S0[k] - 1) * 100), 4),
            "mu": round(float(mu[k]), 6),
            "mu_historical": round(float(mu_hist[k]), 6),
            "sigma": round(float(sigma[k]), 6),
            "p5": round(float(p5[k]), 4),
            "p25": round(float(p25[k]), 4),
            "p50": round(float(p50[k]), 4),
            "p75": round(float(p75[k]), 4),
            "p95": round(float(p95[k]), 4),
            "percentile_rank": round(float(ranks[k]), 2),
            "inside_50": bool(inside_50[k]),
            "inside_90": bool(inside_90[k]),
        }
        for k, i in enumerate(idx)
    ]

    settings = _settings(h, lookback, n_sims, seed, drift, rate, data.currency, "rolling")
    settings["n_windows_requested"] = int(n_windows)
    return {
        "metadata": _metadata(data, dates),
        "settings": settings,
        "summary": {
            "n_windows": int(idx.size),
            "first_start_date": _iso(dates[idx[0]]),
            "last_start_date": _iso(dates[idx[-1]]),
            "coverage_50": round(float(inside_50.mean()), 6),
            "coverage_90": round(float(inside_90.mean()), 6),
            "below_p5": round(float((actual < p5).mean()), 6),
            "above_p95": round(float((actual > p95).mean()), 6),
            "mean_percentile_rank": round(float(ranks.mean()), 2),
            "pit_histogram": {
                "bin_edges": [round(float(e), 4) for e in edges],
                "counts": [int(c) for c in counts],
            },
        },
        "windows": windows,
    }


def rolling_backtest(
    ticker: str,
    horizon: str,
    lookback: str = "2y",
    drift: str = "historical",
    n_windows: int = DEFAULT_WINDOWS,
    n_sims: int = DEFAULT_ROLLING_SIMS,
    seed: int = 42,
    risk_free_rate: float | None = None,
) -> dict[str, Any]:
    """Fetch history once (10+ years), then run a rolling backtest on it."""
    _check_inputs(lookback, drift, risk_free_rate, n_sims)
    if not 1 <= n_windows <= MAX_WINDOWS:
        raise ValueError(f"n_windows must be between 1 and {MAX_WINDOWS}, got {n_windows}")
    data = fetch_price_history(ticker, history_start(horizon, lookback))
    return rolling_backtest_from_prices(data, horizon, lookback=lookback, drift=drift,
                                        n_windows=n_windows, n_sims=n_sims, seed=seed,
                                        risk_free_rate=risk_free_rate)
