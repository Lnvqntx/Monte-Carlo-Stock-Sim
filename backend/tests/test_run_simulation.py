import json

import pytest

import core
from core.data import PriceData
from tests.conftest import make_gbm_prices


@pytest.fixture
def fake_fetch(monkeypatch):
    prices = make_gbm_prices(504, mu=0.1, sigma=0.25, seed=3)
    calls = []

    def _fetch(ticker, lookback="2y"):
        calls.append((ticker, lookback))
        return PriceData(prices, ticker.upper(), "USD", "Test Corp", prices.index[-1].date().isoformat())

    monkeypatch.setattr(core, "fetch_prices", _fetch)
    return calls, prices


def test_end_to_end(fake_fetch):
    calls, prices = fake_fetch
    out = core.run_simulation("test", "3m", n_sims=2000)
    assert calls == [("test", "2y")]
    assert set(out) == {"metadata", "parameters", "settings", "analysis"}
    assert out["metadata"]["ticker"] == "TEST"
    assert out["parameters"]["S0"] == pytest.approx(float(prices.iloc[-1]), abs=1e-4)
    assert out["settings"]["n_steps"] == 63
    assert out["settings"]["n_sims"] == 2000
    assert len(out["analysis"]["mean_path"]) == 64
    assert out["analysis"]["mean_path"][0] == out["parameters"]["S0"]
    json.dumps(out)


def test_reproducible(fake_fetch):
    a = core.run_simulation("test", "1m", n_sims=500, seed=42)
    b = core.run_simulation("test", "1m", n_sims=500, seed=42)
    assert a == b


def test_invalid_horizon_fails_before_fetch(fake_fetch):
    calls, _ = fake_fetch
    with pytest.raises(ValueError):
        core.run_simulation("test", "nonsense")
    assert calls == []
