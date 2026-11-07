"""Price history fetching. All yfinance usage lives here so it can be mocked."""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import yfinance as yf

from .errors import DataFetchError, InsufficientDataError, InvalidTickerError

MIN_TRADING_DAYS = 60

IRX_SYMBOL = "^IRX"  # CBOE 13-week T-bill yield index, quoted in percent (3.7 = 3.7%)
LIVE_RATE_TIMEOUT_SECONDS = 3.0


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


def _normalize_symbol(ticker: str) -> str:
    symbol = (ticker or "").strip().upper()
    if not symbol:
        raise InvalidTickerError("Ticker must be a non-empty string")
    return symbol


def _download(symbol: str, **history_kwargs: Any) -> tuple[Any, pd.DataFrame]:
    try:
        t = yf.Ticker(symbol)
        df = t.history(interval="1d", auto_adjust=True, **history_kwargs)
    except Exception as exc:  # yfinance raises a variety of network/HTTP errors
        raise DataFetchError(f"Failed to fetch data for {symbol}: {exc}") from exc
    return t, df


def _to_price_data(t: Any, df: pd.DataFrame | None, symbol: str) -> PriceData:
    """Clean a yfinance history frame into PriceData, raising the usual errors."""
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


def fetch_prices(ticker: str, lookback: str = "2y") -> PriceData:
    """Fetch adjusted daily close prices for `ticker` over `lookback` (yfinance period).

    Raises InvalidTickerError (no data), InsufficientDataError (< 60 days)
    or DataFetchError (network / provider failure).
    """
    symbol = _normalize_symbol(ticker)
    t, df = _download(symbol, period=lookback)
    return _to_price_data(t, df, symbol)


def fetch_price_history(
    ticker: str,
    start: date | str,
    end: date | str | None = None,
) -> PriceData:
    """Fetch adjusted daily closes from `start` (inclusive) to `end` (exclusive; default today).

    Used by the backtester, which downloads one long window once and slices it locally.
    Raises the same errors as fetch_prices.
    """
    symbol = _normalize_symbol(ticker)
    kwargs: dict[str, Any] = {"start": pd.Timestamp(start).date().isoformat()}
    if end is not None:
        kwargs["end"] = pd.Timestamp(end).date().isoformat()
    t, df = _download(symbol, **kwargs)
    return _to_price_data(t, df, symbol)


def _download_irx(timeout: float) -> float | None:
    df = yf.Ticker(IRX_SYMBOL).history(period="5d", interval="1d", auto_adjust=False,
                                       timeout=timeout)
    if df is None or df.empty or "Close" not in df.columns:
        return None
    closes = df["Close"].dropna()
    if closes.empty:
        return None
    return float(closes.iloc[-1]) / 100.0


def fetch_live_tbill_rate(timeout: float = LIVE_RATE_TIMEOUT_SECONDS) -> float | None:
    """Latest 13-week US T-bill yield from ^IRX as a decimal (0.037), or None on any failure.

    Never raises and never waits longer than about `timeout` seconds, so callers can fall
    back to a default rate silently.
    """
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        value = pool.submit(_download_irx, timeout).result(timeout=timeout)
    except Exception:
        return None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    # Reject garbage quotes (same bounds as user overrides in core.rates).
    if value is None or not math.isfinite(value) or not -0.05 <= value <= 0.25:
        return None
    return value
