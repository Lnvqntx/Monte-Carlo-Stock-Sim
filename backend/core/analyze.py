"""Summarize simulated paths into JSON-serializable risk statistics."""

from __future__ import annotations

from typing import Any

import numpy as np

PRICE_DECIMALS = 4
PCT_DECIMALS = 4
BAND_PERCENTILES = (5, 25, 50, 75, 95)


def _r(x: float, nd: int = PRICE_DECIMALS) -> float:
    """Round to a plain Python float."""
    return round(float(x), nd)


def _rl(arr: np.ndarray, nd: int = PRICE_DECIMALS) -> list[float]:
    """Round an array to a list of plain Python floats."""
    return [round(float(v), nd) for v in np.asarray(arr).ravel()]


def analyze(
    paths: np.ndarray,
    S0: float,
    n_sample_paths: int = 100,
    n_bins: int = 50,
    seed: int | None = 42,
) -> dict[str, Any]:
    """Compute final-price stats, risk metrics, percentile bands, sample paths and a histogram.

    `var_95_pct` is the loss (as % of S0) at the 5th percentile final price;
    a negative value means even the 5th percentile ends above S0.
    """
    paths = np.asarray(paths, dtype=float)
    if paths.ndim != 2 or paths.shape[1] < 2:
        raise ValueError("paths must have shape (n_sims, n_steps + 1) with n_steps >= 1")
    S0 = float(S0)
    final = paths[:, -1]

    p5, p25, p50, p75, p95 = np.percentile(final, BAND_PERCENTILES)
    final_stats = {
        "mean": _r(final.mean()),
        "median": _r(p50),
        "p5": _r(p5),
        "p25": _r(p25),
        "p75": _r(p75),
        "p95": _r(p95),
        "min": _r(final.min()),
        "max": _r(final.max()),
    }

    bands_arr = np.percentile(paths, BAND_PERCENTILES, axis=0)
    bands = {f"p{p}": _rl(row) for p, row in zip(BAND_PERCENTILES, bands_arr)}

    rng = np.random.default_rng(seed)
    k = min(n_sample_paths, paths.shape[0])
    idx = np.sort(rng.choice(paths.shape[0], size=k, replace=False))
    sample_paths = [_rl(paths[i]) for i in idx]

    counts, edges = np.histogram(final, bins=n_bins)

    return {
        "final_price": final_stats,
        "expected_return_pct": _r((final.mean() / S0 - 1.0) * 100, PCT_DECIMALS),
        "prob_below_start": _r(np.mean(final < S0), 6),
        "var_95_pct": _r((S0 - p5) / S0 * 100, PCT_DECIMALS),
        "bands": bands,
        "mean_path": _rl(paths.mean(axis=0)),
        "sample_paths": sample_paths,
        "sample_path_indices": [int(i) for i in idx],
        "histogram": {
            "bin_edges": _rl(edges),
            "counts": [int(c) for c in counts],
        },
    }
