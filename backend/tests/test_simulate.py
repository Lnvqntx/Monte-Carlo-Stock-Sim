import numpy as np
import pytest

from core.simulate import simulate_gbm


def test_shape_and_first_column():
    paths = simulate_gbm(100.0, 0.1, 0.2, T=0.5, n_steps=126, n_sims=500)
    assert paths.shape == (500, 127)
    assert np.all(paths[:, 0] == 100.0)
    assert np.all(paths > 0)


def test_same_seed_identical():
    a = simulate_gbm(100.0, 0.1, 0.2, 1.0, 252, 1000, seed=42)
    b = simulate_gbm(100.0, 0.1, 0.2, 1.0, 252, 1000, seed=42)
    np.testing.assert_array_equal(a, b)


def test_different_seed_differs():
    a = simulate_gbm(100.0, 0.1, 0.2, 1.0, 252, 1000, seed=42)
    b = simulate_gbm(100.0, 0.1, 0.2, 1.0, 252, 1000, seed=43)
    assert not np.array_equal(a, b)


@pytest.mark.parametrize("mu, sigma, T", [(0.10, 0.20, 1.0), (0.25, 0.40, 2.0), (-0.05, 0.15, 0.5)])
def test_mean_final_matches_drift(mu, sigma, T):
    S0 = 100.0
    paths = simulate_gbm(S0, mu, sigma, T, n_steps=int(252 * T), n_sims=10_000, seed=42)
    expected = S0 * np.exp(mu * T)
    # standard error of the mean is ~ expected * sqrt(exp(sigma^2 T) - 1) / 100
    se = expected * np.sqrt(np.exp(sigma**2 * T) - 1) / np.sqrt(10_000)
    assert abs(paths[:, -1].mean() - expected) < 4 * se


def test_zero_vol_is_deterministic():
    paths = simulate_gbm(100.0, 0.1, 0.0, 1.0, 252, 10)
    np.testing.assert_allclose(paths[:, -1], 100.0 * np.exp(0.1))


@pytest.mark.parametrize("kwargs", [dict(S0=0), dict(sigma=-0.1), dict(T=0), dict(n_steps=0), dict(n_sims=0)])
def test_invalid_args(kwargs):
    base = dict(S0=100.0, mu=0.1, sigma=0.2, T=1.0, n_steps=10, n_sims=10)
    base.update(kwargs)
    with pytest.raises(ValueError):
        simulate_gbm(**base)
