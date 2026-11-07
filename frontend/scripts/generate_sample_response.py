"""Generate mocks/sample-response.json for NEXT_PUBLIC_DEMO_MODE.

Runs the real backend pipeline (core estimate -> simulate -> analyze, then api.serialize)
on synthetic daily closes, so the file has exactly the shape POST /api/simulate returns.
No network access needed.

Run from frontend/ with the backend virtualenv active:
    python scripts/generate_sample_response.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from api.serialize import serialize_result  # noqa: E402
from core import TRADING_DAYS_PER_YEAR, analyze, estimate_parameters, parse_horizon, simulate_gbm  # noqa: E402

TICKER, LONG_NAME, CURRENCY = "AAPL", "Apple Inc.", "USD"
HORIZON, LOOKBACK, N_SIMS, SEED = "6m", "2y", 10_000, 42
LAST_DATE = "2026-11-06"


def synthetic_prices(n: int = 502, start: float = 172.0) -> pd.Series:
    """Two years of business-day closes from a GBM with realistic large-cap parameters."""
    rng = np.random.default_rng(2026)
    dt = 1 / TRADING_DAYS_PER_YEAR
    mu, sigma = 0.16, 0.27
    r = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n - 1)
    values = start * np.exp(np.concatenate([[0.0], np.cumsum(r)]))
    index = pd.bdate_range(end=LAST_DATE, periods=n)
    return pd.Series(np.round(values, 2), index=index, name=TICKER)


def main() -> None:
    prices = synthetic_prices()
    params = estimate_parameters(prices)
    h = parse_horizon(HORIZON)
    paths = simulate_gbm(params.S0, params.mu, params.sigma, h.T, h.n_days, N_SIMS, SEED)
    result = {
        "metadata": {
            "ticker": TICKER,
            "currency": CURRENCY,
            "long_name": LONG_NAME,
            "last_date": LAST_DATE,
            "n_prices": int(len(prices)),
        },
        "parameters": params.to_dict(),
        "settings": {
            "horizon": h.label,
            "n_steps": h.n_days,
            "T_years": round(h.T, 6),
            "lookback": LOOKBACK,
            "n_sims": N_SIMS,
            "seed": SEED,
            "trading_days_per_year": TRADING_DAYS_PER_YEAR,
            "drift": "historical",
        },
        "analysis": analyze(paths, params.S0, seed=SEED),
    }
    out = Path(__file__).resolve().parents[1] / "mocks" / "sample-response.json"
    out.write_text(json.dumps(serialize_result(result), separators=(",", ":")) + "\n")
    print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
