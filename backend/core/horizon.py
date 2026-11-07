"""Parse forecast horizons like "1w", "3m", "1y" into trading days."""

from __future__ import annotations

import re
from dataclasses import dataclass

TRADING_DAYS_PER_YEAR = 252
_UNIT_DAYS = {"d": 1, "w": 5, "m": 21, "y": 252}
_PATTERN = re.compile(r"^\s*(\d+)\s*([dwmy])\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Horizon:
    """A forecast horizon in trading days and years."""

    label: str
    n_days: int
    T: float


def parse_horizon(text: str) -> Horizon:
    """Convert e.g. "6m" to Horizon(n_days=126, T=0.5).

    Units: d = 1, w = 5, m = 21, y = 252 trading days.
    Raises ValueError for malformed or non-positive input.
    """
    if not isinstance(text, str):
        raise ValueError(f"Horizon must be a string like '3m', got {text!r}")
    match = _PATTERN.match(text)
    if not match:
        raise ValueError(
            f"Invalid horizon {text!r}; use <number><unit> with unit d, w, m or y (e.g. '3m')"
        )
    amount, unit = int(match.group(1)), match.group(2).lower()
    if amount <= 0:
        raise ValueError(f"Horizon must be positive, got {text!r}")
    n_days = amount * _UNIT_DAYS[unit]
    return Horizon(label=f"{amount}{unit}", n_days=n_days, T=n_days / TRADING_DAYS_PER_YEAR)
