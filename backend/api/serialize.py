"""Trim a core.run_simulation result into a browser-friendly payload."""

from __future__ import annotations

from typing import Any

import numpy as np

MAX_POINTS = 200
N_SAMPLE_PATHS = 50


def downsample_indices(n_points: int, max_points: int = MAX_POINTS) -> list[int]:
    """Evenly spaced indices into a series of length `n_points`, always keeping first and last."""
    if n_points <= 0:
        return []
    if n_points <= max_points:
        return list(range(n_points))
    idx = np.unique(np.round(np.linspace(0, n_points - 1, max_points)).astype(int))
    return [int(i) for i in idx]


def _take(series: list[float], idx: list[int]) -> list[float]:
    return [series[i] for i in idx]


def serialize_result(
    result: dict[str, Any],
    max_points: int = MAX_POINTS,
    n_sample_paths: int = N_SAMPLE_PATHS,
) -> dict[str, Any]:
    """Downsample time series to <= `max_points` and keep `n_sample_paths` sample paths.

    Scalar stats, the histogram, metadata, parameters and settings are passed through unchanged.
    `analysis.days` holds the trading-day index (0 = today) of every kept point.
    """
    analysis = result["analysis"]
    n_points = len(analysis["mean_path"])
    idx = downsample_indices(n_points, max_points)

    # Evenly spread picks over the (already randomly chosen) sample paths.
    all_paths = analysis["sample_paths"]
    all_path_ids = analysis.get("sample_path_indices") or list(range(len(all_paths)))
    k = min(n_sample_paths, len(all_paths))
    pick = downsample_indices(len(all_paths), k) if k else []

    trimmed = {
        "final_price": analysis["final_price"],
        "expected_return_pct": analysis["expected_return_pct"],
        "prob_below_start": analysis["prob_below_start"],
        "var_95_pct": analysis["var_95_pct"],
        "histogram": analysis["histogram"],
        "days": idx,
        "mean_path": _take(analysis["mean_path"], idx),
        "bands": {name: _take(series, idx) for name, series in analysis["bands"].items()},
        "sample_paths": [_take(all_paths[i], idx) for i in pick],
        "sample_path_indices": [all_path_ids[i] for i in pick],
    }
    return {
        "metadata": result["metadata"],
        "parameters": result["parameters"],
        "settings": result["settings"],
        "analysis": trimmed,
    }
