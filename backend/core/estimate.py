"""Estimate GBM parameters from historical prices."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .errors import InsufficientDataError
from .horizon import TRADING_DAYS_PER_YEAR


@dataclass(frozen=True)
class Parameters:
    """Estimated GBM parameters (annualized)."""

    S0: float
    log_returns: np.ndarray
    mu: float
    sigma: float

    def to_dict(self) -> dict[str, float | int]:
        """JSON-friendly summary (omits the raw returns)."""
        return {
            "S0": round(self.S0, 4),
            "mu": round(self.mu, 6),
            "sigma": round(self.sigma, 6),
            "n_returns": int(self.log_returns.size),
        }


def estimate_parameters(prices: pd.Series | np.ndarray) -> Parameters:
    """Estimate S0, annualized sigma and arithmetic drift mu from daily closes.

    sigma = std(log r, ddof=1) * sqrt(252); mu = mean(log r) * 252 + sigma**2 / 2.
    """
    values = np.asarray(prices, dtype=float)
    values = values[np.isfinite(values)]
    if values.size < 3:
        raise InsufficientDataError("Need at least 3 prices to estimate parameters")
    if np.any(values <= 0):
        raise ValueError("Prices must be strictly positive")

    log_returns = np.diff(np.log(values))
    sigma = float(np.std(log_returns, ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
    mu = float(np.mean(log_returns) * TRADING_DAYS_PER_YEAR + 0.5 * sigma**2)
    return Parameters(S0=float(values[-1]), log_returns=log_returns, mu=mu, sigma=sigma)
