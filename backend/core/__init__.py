"""Monte Carlo GBM stock price simulator - core library."""

from __future__ import annotations

from typing import Any

from .analyze import analyze
from .data import PriceData, fetch_price_history, fetch_prices
from .errors import (
    DataFetchError,
    InsufficientDataError,
    InvalidTickerError,
    SimulatorError,
)
from .estimate import Parameters, estimate_parameters
from .horizon import TRADING_DAYS_PER_YEAR, Horizon, parse_horizon
from .rates import RiskFreeRate, infer_currency, resolve_risk_free_rate, validate_rate
from .simulate import simulate_gbm

__all__ = [
    "run_simulation",
    "simulate_from_prices",
    "DRIFT_MODELS",
    "RiskFreeRate",
    "resolve_risk_free_rate",
    "validate_rate",
    "fetch_prices",
    "fetch_price_history",
    "single_backtest",
    "rolling_backtest",
    "single_backtest_from_prices",
    "rolling_backtest_from_prices",
    "BacktestDateError",
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


DRIFT_MODELS = ("historical", "risk_free")


def _check_drift(drift: str, risk_free_rate: float | None) -> None:
    if drift not in DRIFT_MODELS:
        raise ValueError(f"drift must be one of {', '.join(DRIFT_MODELS)}, got {drift!r}")
    if risk_free_rate is not None:
        if drift != "risk_free":
            raise ValueError("risk_free_rate can only be set when drift is 'risk_free'")
        validate_rate(risk_free_rate)


def simulate_from_prices(
    data: PriceData,
    horizon: str,
    lookback: str = "2y",
    n_sims: int = 10_000,
    seed: int = 42,
    drift: str = "historical",
    risk_free_rate: float | None = None,
) -> dict[str, Any]:
    """Estimate, simulate and analyze already-fetched prices. Returns a JSON-ready dict.

    drift="historical" uses the mu estimated from log returns; drift="risk_free" uses the
    annual risk-free rate r instead (risk-neutral GBM). Sigma always comes from history, and
    the historical mu is returned either way as parameters.mu_historical.
    """
    if n_sims < 1:
        raise ValueError("n_sims must be >= 1")
    _check_drift(drift, risk_free_rate)
    h = parse_horizon(horizon)
    params = estimate_parameters(data.prices)

    rate: RiskFreeRate | None = None
    if drift == "risk_free":
        rate = resolve_risk_free_rate(infer_currency(data.ticker, data.currency), risk_free_rate)
        mu = rate.rate
    else:
        mu = params.mu

    paths = simulate_gbm(params.S0, mu, params.sigma, h.T, h.n_days, n_sims, seed)
    parameters = params.to_dict()
    parameters["mu"] = round(mu, 6)  # the drift actually simulated
    parameters["mu_historical"] = round(params.mu, 6)
    return {
        "metadata": data.metadata(),
        "parameters": parameters,
        "settings": {
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
        },
        "analysis": analyze(paths, params.S0, seed=seed),
    }


def run_simulation(
    ticker: str,
    horizon: str,
    lookback: str = "2y",
    n_sims: int = 10_000,
    seed: int = 42,
    drift: str = "historical",
    risk_free_rate: float | None = None,
) -> dict[str, Any]:
    """Fetch history, estimate GBM parameters, simulate and analyze. Returns a JSON-ready dict.

    See simulate_from_prices for the drift options.
    """
    if n_sims < 1:
        raise ValueError("n_sims must be >= 1")
    parse_horizon(horizon)  # validate before any network call
    _check_drift(drift, risk_free_rate)
    data = fetch_prices(ticker, lookback=lookback)
    return simulate_from_prices(data, horizon, lookback=lookback, n_sims=n_sims, seed=seed,
                                drift=drift, risk_free_rate=risk_free_rate)


from .backtest import (  # noqa: E402  (needs _check_drift defined above)
    BacktestDateError,
    rolling_backtest,
    rolling_backtest_from_prices,
    single_backtest,
    single_backtest_from_prices,
)
