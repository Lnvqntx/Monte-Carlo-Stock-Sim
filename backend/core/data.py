"""Price history fetching. All yfinance usage lives here so it can be mocked."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import yfinance as yf

from .errors import DataFetchError, InsufficientDataError, InvalidTickerError

MIN_TRADING_DAYS = 60


@dataclass(frozen=True)
class PriceData:
    """Cleaned close prices plus ticker metadata."""

    prices: pd.Series
    ticker: str
    currency: str | None
    long_name: str | None
    last_date: str

    def metadata(self) -> dict[str, Any]:
        """JSON-friendly metadata (no price series)."""
        return {
            "ticker": self.ticker,
            "currency": self.currency,
            "long_name": self.long_name,
            "last_date": self.last_date,
            "n_prices": int(len(self.prices)),
        }


def _lookup_metadata(t: Any) -> tuple[str | None, str | None]:
    """Best-effort currency and long name; never raises."""
    meta: dict[str, Any] = {}
    try:
        meta = dict(getattr(t, "history_metadata", None) or {})
    except Exception:
        meta = {}
    currency = meta.get("currency")
    long_name = meta.get("longName")
    if currency is None or long_name is None:
        try:
            info = t.info or {}
            currency = currency or info.get("currency")
            long_name = long_name or info.get("longName") or info.get("shortName")
        except Exception:
            pass
    return currency, long_name


def fetch_prices(ticker: str, lookback: str = "2y") -> PriceData:
    """Fetch adjusted daily close prices for `ticker` over `lookback` (yfinance period).

    Raises InvalidTickerError (no data), InsufficientDataError (< 60 days)
    or DataFetchError (network / provider failure).
    """
    symbol = (ticker or "").strip().upper()
    if not symbol:
        raise InvalidTickerError("Ticker must be a non-empty string")

    try:
        t = yf.Ticker(symbol)
        df = t.history(period=lookback, interval="1d", auto_adjust=True)
    except Exception as exc:  # yfinance raises a variety of network/HTTP errors
        raise DataFetchError(f"Failed to fetch data for {symbol}: {exc}") from exc

    if df is None or df.empty or "Close" not in df.columns:
        raise InvalidTickerError(f"No price data found for ticker {symbol!r}")

    prices = df["Close"].dropna().astype(float)
    if prices.empty:
        raise InvalidTickerError(f"No price data found for ticker {symbol!r}")
    if len(prices) < MIN_TRADING_DAYS:
        raise InsufficientDataError(
            f"Only {len(prices)} trading days for {symbol}; need at least {MIN_TRADING_DAYS}"
        )

    prices.name = symbol
    currency, long_name = _lookup_metadata(t)
    last_date = pd.Timestamp(prices.index[-1]).date().isoformat()
    return PriceData(prices, symbol, currency, long_name, last_date)
