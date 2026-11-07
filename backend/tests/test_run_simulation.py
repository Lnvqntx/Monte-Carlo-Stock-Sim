import math
import json

import pytest

import core
from core.data import PriceData
from core.rates import DEFAULT_RATES
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


# --- drift models ---------------------------------------------------------------

def test_historical_is_default_and_unchanged(fake_fetch):
    default = core.run_simulation("test", "6m", n_sims=2000)
    explicit = core.run_simulation("test", "6m", n_sims=2000, drift="historical")
    assert default == explicit
    p, s = default["parameters"], default["settings"]
    assert p["mu"] == p["mu_historical"]
    assert s["drift"] == "historical"
    assert s["risk_free_rate"] is None and s["rate_source"] is None
    # Same paths as simulating with the estimated mu directly.
    est = core.estimate_parameters(fake_fetch[1])
    h = core.parse_horizon("6m")
    paths = core.simulate_gbm(est.S0, est.mu, est.sigma, h.T, h.n_days, 2000, 42)
    assert default["analysis"] == core.analyze(paths, est.S0, seed=42)


def test_risk_free_mean_matches_s0_exp_rt(fake_fetch):
    r, n = 0.045, 20_000
    out = core.run_simulation("test", "1y", n_sims=n, drift="risk_free", risk_free_rate=r)
    p, s = out["parameters"], out["settings"]
    assert p["mu"] == r
    assert p["mu_historical"] != r
    assert (s["drift"], s["risk_free_rate"], s["rate_source"]) == ("risk_free", r, "user override")

    S0, sigma, T = p["S0"], p["sigma"], s["T_years"]
    expected = S0 * math.exp(r * T)
    # Standard error of the mean of a lognormal final price.
    se = S0 * math.exp(r * T) * math.sqrt(math.exp(sigma**2 * T) - 1) / math.sqrt(n)
    assert abs(out["analysis"]["final_price"]["mean"] - expected) < 4 * se
    assert out["analysis"]["mean_path"][0] == S0


def test_risk_free_keeps_historical_sigma(fake_fetch):
    hist = core.run_simulation("test", "3m", n_sims=500)
    rf = core.run_simulation("test", "3m", n_sims=500, drift="risk_free", risk_free_rate=0.03)
    assert rf["parameters"]["sigma"] == hist["parameters"]["sigma"]
    assert rf["parameters"]["mu_historical"] == hist["parameters"]["mu"]
    assert rf["analysis"] != hist["analysis"]


def test_risk_free_default_rate_by_currency(fake_fetch):
    out = core.run_simulation("test", "1m", n_sims=500, drift="risk_free")
    assert out["settings"]["rate_source"] == "default for USD"  # live lookup mocked to fail
    assert out["parameters"]["mu"] == DEFAULT_RATES["USD"]


def test_risk_free_uses_live_rate_when_available(fake_fetch, monkeypatch):
    monkeypatch.setattr("core.rates.fetch_live_tbill_rate", lambda: 0.0391)
    out = core.run_simulation("test", "1m", n_sims=500, drift="risk_free")
    assert (out["settings"]["risk_free_rate"], out["settings"]["rate_source"]) == (0.0391,
                                                                                  "live ^IRX")


def test_risk_free_indian_ticker_without_currency(monkeypatch):
    prices = make_gbm_prices(300, seed=5)
    monkeypatch.setattr(core, "fetch_prices", lambda t, lookback="2y": PriceData(
        prices, t.upper(), None, None, prices.index[-1].date().isoformat()))
    out = core.run_simulation("tcs.ns", "1m", n_sims=500, drift="risk_free")
    assert out["settings"]["rate_source"] == "default for INR"
    assert out["parameters"]["mu"] == DEFAULT_RATES["INR"]


@pytest.mark.parametrize("kwargs", [
    dict(drift="neutral"),
    dict(drift="risk_free", risk_free_rate=0.3),
    dict(drift="risk_free", risk_free_rate=-0.06),
    dict(drift="historical", risk_free_rate=0.04),
])
def test_bad_drift_or_rate_fails_before_fetch(fake_fetch, kwargs):
    calls, _ = fake_fetch
    with pytest.raises(ValueError):
        core.run_simulation("test", "1m", **kwargs)
    assert calls == []
