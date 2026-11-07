"""Monte Carlo GBM stock price simulator - core library."""

from __future__ import annotations

from typing import Any

from .analyze import analyze
from .data import PriceData, fetch_prices
from .errors import (
    DataFetchError,
    InsufficientDataError,
    InvalidTickerError,
    SimulatorError,
)
from .estimate import Parameters, estimate_parameters
from .horizon import TRADING_DAYS_PER_YEAR, Horizon, parse_horizon
from .simulate import simulate_gbm

__all__ = [
    "run_simulation",
    "fetch_prices",
    "estimate_parameters",
    "simulate_gbm",
    "analyze",
    "parse_horizon",
    "PriceData",
    "Parameters",
    "Horizon",
    "TRADING_DAYS_PER_YEAR",
    "SimulatorError",
    "InvalidTickerError",
    "InsufficientDataError",
    "DataFetchError",
]


def run_simulation(
    ticker: str,
    horizon: str,
    lookback: str = "2y",
    n_sims: int = 10_000,
    seed: int = 42,
) -> dict[str, Any]:
    """Fetch history, estimate GBM parameters, simulate and analyze. Returns a JSON-ready dict."""
    if n_sims < 1:
        raise ValueError("n_sims must be >= 1")
    h = parse_horizon(horizon)  # validate before any network call
    data = fetch_prices(ticker, lookback=lookback)
    params = estimate_parameters(data.prices)
    paths = simulate_gbm(params.S0, params.mu, params.sigma, h.T, h.n_days, n_sims, seed)
    return {
        "metadata": data.metadata(),
        "parameters": params.to_dict(),
        "settings": {
            "horizon": h.label,
            "n_steps": h.n_days,
            "T_years": round(h.T, 6),
            "lookback": lookback,
            "n_sims": int(n_sims),
            "seed": int(seed),
            "trading_days_per_year": TRADING_DAYS_PER_YEAR,
            "drift": "historical",
        },
        "analysis": analyze(paths, params.S0, seed=seed),
    }
