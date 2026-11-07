"""Generate the NEXT_PUBLIC_DEMO_MODE mocks:
    mocks/sample-response.json            historical drift (the default)
    mocks/sample-response-risk-free.json  risk-free drift at the default USD rate

Runs the real backend pipeline (core.simulate_from_prices, then api.serialize) on synthetic
daily closes, so the files have exactly the shape POST /api/simulate returns.
No network access needed: the live ^IRX lookup is disabled.

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

import core.rates  # noqa: E402
from api.serialize import serialize_result  # noqa: E402
from core import TRADING_DAYS_PER_YEAR, PriceData, simulate_from_prices  # noqa: E402

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
    core.rates.fetch_live_tbill_rate = lambda *a, **k: None  # deterministic: use the USD default
    data = PriceData(synthetic_prices(), TICKER, CURRENCY, LONG_NAME, LAST_DATE)
    mocks = Path(__file__).resolve().parents[1] / "mocks"
    for name, drift in (("sample-response.json", "historical"),
                        ("sample-response-risk-free.json", "risk_free")):
        result = simulate_from_prices(data, HORIZON, lookback=LOOKBACK, n_sims=N_SIMS, seed=SEED,
                                      drift=drift)
        out = mocks / name
        out.write_text(json.dumps(serialize_result(result), separators=(",", ":")) + "\n")
        print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
