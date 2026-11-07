import numpy as np
import pytest

from core.errors import InsufficientDataError
from core.estimate import estimate_parameters
from tests.conftest import make_gbm_prices


def test_recovers_known_mu_and_sigma():
    mu, sigma = 0.12, 0.30
    prices = make_gbm_prices(252 * 50, mu=mu, sigma=sigma, seed=7)
    p = estimate_parameters(prices)
    assert p.sigma == pytest.approx(sigma, rel=0.03)
    # drift standard error ~ sigma / sqrt(years) ~ 0.04
    assert p.mu == pytest.approx(mu, abs=0.1)
    assert p.S0 == pytest.approx(float(prices.iloc[-1]))
    assert p.log_returns.size == len(prices) - 1


def test_formula_matches_definition():
    prices = make_gbm_prices(300, seed=1)
    lr = np.diff(np.log(prices.to_numpy()))
    p = estimate_parameters(prices)
    sig = lr.std(ddof=1) * np.sqrt(252)
    assert p.sigma == pytest.approx(sig)
    assert p.mu == pytest.approx(lr.mean() * 252 + 0.5 * sig**2)


def test_rejects_bad_input():
    with pytest.raises(InsufficientDataError):
        estimate_parameters([100.0, 101.0])
    with pytest.raises(ValueError):
        estimate_parameters([100.0, 0.0, 101.0, 102.0])
