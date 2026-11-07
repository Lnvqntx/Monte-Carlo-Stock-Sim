"""Risk-free rate defaults and resolution for the risk-neutral drift option.

All rates are annual decimals (0.037 = 3.7% a year) and are used directly as the GBM drift,
so E[S_T] = S0 * exp(r * T). T-bill yields are quoted on a discount / simple basis; the gap to
a continuously compounded rate is a few basis points at these levels, far below the noise of
a Monte Carlo run, so no conversion is applied.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .data import IRX_SYMBOL, fetch_live_tbill_rate

# --- Defaults: update these together and bump RATES_AS_OF ---------------------------
# As of 2026-11 (latest published figures found then were mid-2026):
#   USD: US 13-week Treasury bill, ~3.67-3.76% in Jun-Jul 2026 auctions.
#   INR: India 91-day Treasury bill, RBI auction cut-offs ~5.25-5.34% in mid-2026.
# For USD the live ^IRX quote is tried first; these values are the fallback.
RATES_AS_OF = "2026-11"
DEFAULT_RATES: dict[str, float] = {
    "USD": 0.0370,
    "INR": 0.0535,
}
# Used for any other (or unknown) currency: a round mid-range short rate.
GENERIC_DEFAULT_RATE = 0.0400

MIN_RATE = -0.05
MAX_RATE = 0.25

SOURCE_OVERRIDE = "user override"
SOURCE_LIVE_IRX = f"live {IRX_SYMBOL}"
SOURCE_GENERIC = "generic default"

INDIAN_SUFFIXES = (".NS", ".BO")


@dataclass(frozen=True)
class RiskFreeRate:
    """An annual risk-free rate and where it came from."""

    rate: float
    source: str


def validate_rate(rate: float) -> float:
    """Return `rate` as a float, or raise ValueError if it is not finite or out of range."""
    try:
        value = float(rate)
    except (TypeError, ValueError):
        raise ValueError(f"risk_free_rate must be a number, got {rate!r}") from None
    if not math.isfinite(value) or not MIN_RATE <= value <= MAX_RATE:
        raise ValueError(
            f"risk_free_rate must be a decimal between {MIN_RATE} and {MAX_RATE} "
            f"(e.g. 0.045 for 4.5%), got {rate!r}"
        )
    return value


def infer_currency(ticker: str | None, currency: str | None) -> str | None:
    """The provider's currency code, or INR for .NS / .BO tickers when it is missing."""
    if currency:
        return currency.strip().upper()
    if ticker and ticker.strip().upper().endswith(INDIAN_SUFFIXES):
        return "INR"
    return None


def resolve_risk_free_rate(
    currency: str | None,
    override: float | None = None,
    *,
    allow_live: bool = True,
) -> RiskFreeRate:
    """Pick the risk-free rate: user override > live ^IRX (USD only) > per-currency default."""
    if override is not None:
        return RiskFreeRate(validate_rate(override), SOURCE_OVERRIDE)
    code = (currency or "").strip().upper()
    if code == "USD" and allow_live:
        live = fetch_live_tbill_rate()
        if live is not None:
            return RiskFreeRate(live, SOURCE_LIVE_IRX)
    if code in DEFAULT_RATES:
        return RiskFreeRate(DEFAULT_RATES[code], f"default for {code}")
    return RiskFreeRate(GENERIC_DEFAULT_RATE, SOURCE_GENERIC)
