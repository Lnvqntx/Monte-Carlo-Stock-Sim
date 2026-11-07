import math

import pytest

from core import rates
from core.rates import (
    DEFAULT_RATES,
    GENERIC_DEFAULT_RATE,
    infer_currency,
    resolve_risk_free_rate,
    validate_rate,
)


@pytest.mark.parametrize("rate", [-0.05, 0.0, 0.045, 0.25])
def test_validate_rate_accepts_bounds(rate):
    assert validate_rate(rate) == rate


@pytest.mark.parametrize("rate", [-0.0501, 0.2501, 4.5, math.nan, math.inf, "abc", None])
def test_validate_rate_rejects(rate):
    with pytest.raises(ValueError):
        validate_rate(rate)


def test_defaults_are_sane():
    assert set(DEFAULT_RATES) == {"USD", "INR"}
    for r in (*DEFAULT_RATES.values(), GENERIC_DEFAULT_RATE):
        assert 0 < r < 0.15
    assert rates.RATES_AS_OF


def test_override_wins_and_skips_live(monkeypatch):
    monkeypatch.setattr(rates, "fetch_live_tbill_rate", lambda: pytest.fail("live fetched"))
    r = resolve_risk_free_rate("USD", 0.045)
    assert (r.rate, r.source) == (0.045, "user override")


def test_override_validated():
    with pytest.raises(ValueError):
        resolve_risk_free_rate("USD", 0.5)


def test_usd_uses_live_irx(monkeypatch):
    monkeypatch.setattr(rates, "fetch_live_tbill_rate", lambda: 0.0412)
    r = resolve_risk_free_rate("usd")
    assert (r.rate, r.source) == (0.0412, "live ^IRX")


def test_usd_falls_back_to_default_when_live_fails():
    # conftest's autouse fixture makes the live lookup return None
    r = resolve_risk_free_rate("USD")
    assert (r.rate, r.source) == (DEFAULT_RATES["USD"], "default for USD")


def test_usd_without_live(monkeypatch):
    monkeypatch.setattr(rates, "fetch_live_tbill_rate", lambda: pytest.fail("live fetched"))
    assert resolve_risk_free_rate("USD", allow_live=False).source == "default for USD"


def test_inr_default_never_fetches_live(monkeypatch):
    monkeypatch.setattr(rates, "fetch_live_tbill_rate", lambda: pytest.fail("live fetched"))
    r = resolve_risk_free_rate("INR")
    assert (r.rate, r.source) == (DEFAULT_RATES["INR"], "default for INR")


@pytest.mark.parametrize("currency", ["EUR", "GBp", None, ""])
def test_other_currencies_use_generic_default(currency):
    r = resolve_risk_free_rate(currency)
    assert (r.rate, r.source) == (GENERIC_DEFAULT_RATE, "generic default")


@pytest.mark.parametrize("ticker,currency,expected", [
    ("AAPL", "USD", "USD"),
    ("RELIANCE.NS", None, "INR"),
    ("TCS.bo", "", "INR"),
    ("TCS.NS", "inr", "INR"),
    ("SAP.DE", None, None),
])
def test_infer_currency(ticker, currency, expected):
    assert infer_currency(ticker, currency) == expected
