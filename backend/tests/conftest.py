"""Shared fixtures: synthetic GBM price series and a fake yfinance Ticker."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_gbm_prices(
    n_days: int, mu: float = 0.10, sigma: float = 0.25, S0: float = 100.0, seed: int = 0
) -> pd.Series:
    """Synthetic daily GBM closes indexed by business days."""
    rng = np.random.default_rng(seed)
    dt = 1 / 252
    inc = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n_days - 1)
    values = S0 * np.exp(np.concatenate([[0.0], np.cumsum(inc)]))
    index = pd.bdate_range("2020-01-01", periods=n_days)
    return pd.Series(values, index=index, name="Close")


class FakeTicker:
    """Stand-in for yfinance.Ticker returning a preset DataFrame."""

    def __init__(self, df: pd.DataFrame, meta: dict | None = None, exc: Exception | None = None):
        self._df, self._exc = df, exc
        self.history_metadata = meta or {}
        self.info: dict = {}
        self.calls: list[dict] = []

    def history(self, **kwargs):
        self.calls.append(kwargs)
        if self._exc:
            raise self._exc
        return self._df


@pytest.fixture
def patch_yf(monkeypatch):
    """Patch core.data.yf.Ticker to return a FakeTicker; returns a setter."""
    import core.data as data_mod

    def _install(df: pd.DataFrame, meta: dict | None = None, exc: Exception | None = None):
        fake = FakeTicker(df, meta, exc)
        monkeypatch.setattr(data_mod.yf, "Ticker", lambda symbol: fake)
        return fake

    return _install


@pytest.fixture(autouse=True)
def no_live_rate(monkeypatch):
    """Never hit Yahoo for ^IRX in tests: the live T-bill lookup reports "unavailable".

    Tests that exercise the live path patch core.rates.fetch_live_tbill_rate themselves.
    """
    monkeypatch.setattr("core.rates.fetch_live_tbill_rate", lambda *a, **k: None)
