"""Generate the NEXT_PUBLIC_DEMO_MODE mocks:
    mocks/sample-response.json            historical drift (the default)
    mocks/sample-response-risk-free.json  risk-free drift at the default USD rate
    mocks/sample-backtest-single.json     POST /api/backtest mode "single"
    mocks/sample-backtest-rolling.json    POST /api/backtest mode "rolling"

Runs the real backend pipeline (core.simulate_from_prices / the core.backtest functions, then
api.serialize) on synthetic daily closes, so the files have exactly the shape POST /api/simulate returns.
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
from api.serialize import serialize_backtest, serialize_result  # noqa: E402
from core import (  # noqa: E402
    TRADING_DAYS_PER_YEAR,
    PriceData,
    rolling_backtest_from_prices,
    simulate_from_prices,
    single_backtest_from_prices,
)

TICKER, LONG_NAME, CURRENCY = "AAPL", "Apple Inc.", "USD"
HORIZON, LOOKBACK, N_SIMS, SEED = "6m", "2y", 10_000, 42
LAST_DATE = "2026-11-06"
BACKTEST_START = "2026-04-15"  # about one 6m horizon + two weeks before LAST_DATE


def synthetic_prices(n: int = 502, start: float = 172.0) -> pd.Series:
    """Two years of business-day closes from a GBM with realistic large-cap parameters."""
    rng = np.random.default_rng(2026)
    dt = 1 / TRADING_DAYS_PER_YEAR
    mu, sigma = 0.16, 0.27
    r = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n - 1)
    values = start * np.exp(np.concatenate([[0.0], np.cumsum(r)]))
    index = pd.bdate_range(end=LAST_DATE, periods=n)
    return pd.Series(np.round(values, 2), index=index, name=TICKER)


def synthetic_history(n: int = 2520, end_price: float = 230.0) -> pd.Series:
    """Ten years of closes with volatility regimes and fat-tailed (Student-t) shocks.

    Real returns are not GBM, so a demo backtest should show what that does to calibration:
    calm spells give narrow bands that the next storm breaks out of.
    """
    rng = np.random.default_rng(35)  # picked so the demo shows typical under-coverage
    dt = 1 / TRADING_DAYS_PER_YEAR
    # Volatility drifts between ~15% and ~45% a year in slow regimes.
    regime = np.repeat(rng.choice([0.16, 0.24, 0.42], size=n // 63 + 1, p=[0.45, 0.4, 0.15]), 63)[: n - 1]
    shocks = rng.standard_t(4, n - 1) / np.sqrt(2.0)  # unit variance
    r = (0.14 - 0.5 * regime**2) * dt + regime * np.sqrt(dt) * shocks
    values = np.exp(np.concatenate([[0.0], np.cumsum(r)]))
    values *= end_price / values[-1]
    index = pd.bdate_range(end=LAST_DATE, periods=n)
    return pd.Series(np.round(values, 2), index=index, name=TICKER)


def write(mocks: Path, name: str, payload: dict) -> None:
    out = mocks / name
    out.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


def main() -> None:
    core.rates.fetch_live_tbill_rate = lambda *a, **k: None  # deterministic: use the USD default
    data = PriceData(synthetic_prices(), TICKER, CURRENCY, LONG_NAME, LAST_DATE)
    mocks = Path(__file__).resolve().parents[1] / "mocks"
    for name, drift in (("sample-response.json", "historical"),
                        ("sample-response-risk-free.json", "risk_free")):
        result = simulate_from_prices(data, HORIZON, lookback=LOOKBACK, n_sims=N_SIMS, seed=SEED,
                                      drift=drift)
        write(mocks, name, serialize_result(result))

    history = PriceData(synthetic_history(), TICKER, CURRENCY, LONG_NAME, LAST_DATE)
    single = single_backtest_from_prices(history, BACKTEST_START, HORIZON, lookback=LOOKBACK,
                                         n_sims=N_SIMS, seed=SEED)
    write(mocks, "sample-backtest-single.json", serialize_backtest(single))
    rolling = rolling_backtest_from_prices(history, HORIZON, lookback=LOOKBACK, seed=SEED)
    write(mocks, "sample-backtest-rolling.json", serialize_backtest(rolling))


if __name__ == "__main__":
    main()
