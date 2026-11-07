"""Vectorized geometric Brownian motion simulation."""

from __future__ import annotations

import numpy as np


def simulate_gbm(
    S0: float,
    mu: float,
    sigma: float,
    T: float,
    n_steps: int,
    n_sims: int = 10_000,
    seed: int | None = 42,
) -> np.ndarray:
    """Simulate GBM price paths; returns array of shape (n_sims, n_steps + 1), column 0 = S0."""
    if S0 <= 0:
        raise ValueError("S0 must be positive")
    if sigma < 0:
        raise ValueError("sigma must be non-negative")
    if T <= 0:
        raise ValueError("T must be positive")
    if n_steps < 1 or n_sims < 1:
        raise ValueError("n_steps and n_sims must be >= 1")

    rng = np.random.default_rng(seed)
    dt = T / n_steps
    z = rng.standard_normal((n_sims, n_steps))
    increments = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z
    log_paths = np.concatenate(
        [np.zeros((n_sims, 1)), np.cumsum(increments, axis=1)], axis=1
    )
    return S0 * np.exp(log_paths)
