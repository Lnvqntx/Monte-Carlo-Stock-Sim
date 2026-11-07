"""Pydantic request/response models for the HTTP API."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core import TRADING_DAYS_PER_YEAR, parse_horizon
from core.backtest import DEFAULT_ROLLING_SIMS, DEFAULT_WINDOWS, MAX_WINDOWS, MIN_WINDOWS
from core.rates import MAX_RATE, MIN_RATE

MAX_HORIZON_YEARS = 5
MAX_HORIZON_DAYS = MAX_HORIZON_YEARS * TRADING_DAYS_PER_YEAR
MIN_SIMS = 1_000
MAX_SIMS = 20_000
TICKER_RE = re.compile(r"^[A-Z0-9.\-^=]{1,20}$")

Lookback = Literal["6mo", "1y", "2y", "5y"]
Drift = Literal["historical", "risk_free"]
BacktestMode = Literal["single", "rolling"]
MIN_START_DATE = date(1970, 1, 1)


def validate_ticker(v: str) -> str:
    symbol = v.strip().upper()
    if not symbol:
        raise ValueError("ticker must not be empty")
    if len(symbol) > 20:
        raise ValueError("ticker must be at most 20 characters")
    if not TICKER_RE.match(symbol):
        raise ValueError("ticker may only contain letters, digits and . - ^ =")
    return symbol


def validate_horizon(v: str) -> str:
    h = parse_horizon(v)  # raises ValueError with a readable message
    if h.n_days > MAX_HORIZON_DAYS:
        raise ValueError(f"horizon must be at most {MAX_HORIZON_YEARS}y, got {h.label!r}")
    return h.label


class SimulateRequest(BaseModel):
    """Body of POST /api/simulate."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"ticker": "AAPL", "horizon": "6m"},
                                        {"ticker": "RELIANCE.NS", "horizon": "1y",
                                         "lookback": "5y", "n_sims": 5000, "seed": 7},
                                        {"ticker": "AAPL", "horizon": "1y", "drift": "risk_free",
                                         "risk_free_rate": 0.045}]},
    )

    ticker: str = Field(..., description="Stock symbol, e.g. AAPL or RELIANCE.NS / TCS.BO")
    horizon: str = Field(..., description="Forecast horizon, e.g. 1w, 3m, 6m, 1y (max 5y)")
    lookback: Lookback = Field("2y", description="History window used to estimate parameters")
    n_sims: int = Field(10_000, ge=MIN_SIMS, le=MAX_SIMS, description="Number of simulated paths")
    seed: int = Field(42, ge=0, description="Random seed (non-negative integer)")
    drift: Drift = Field("historical", description=(
        "historical: drift estimated from past log returns. risk_free: drift = the annual "
        "risk-free rate (risk-neutral GBM); volatility is still estimated from history."))
    risk_free_rate: float | None = Field(
        None, ge=MIN_RATE, le=MAX_RATE, allow_inf_nan=False,
        description=("Annual risk-free rate as a decimal (0.045 = 4.5%), only with "
                     "drift=risk_free. Default: live 13-week T-bill (^IRX) for USD, "
                     "else a per-currency default."))

    @field_validator("ticker")
    @classmethod
    def _check_ticker(cls, v: str) -> str:
        return validate_ticker(v)

    @field_validator("horizon")
    @classmethod
    def _check_horizon(cls, v: str) -> str:
        return validate_horizon(v)

    @model_validator(mode="after")
    def _check_rate_needs_risk_free(self) -> "SimulateRequest":
        if self.risk_free_rate is not None and self.drift != "risk_free":
            raise ValueError("risk_free_rate can only be set when drift is 'risk_free'")
        return self


class BacktestRequest(BaseModel):
    """Body of POST /api/backtest."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [
            {"mode": "single", "ticker": "AAPL", "horizon": "6m", "start_date": "2025-05-01"},
            {"mode": "rolling", "ticker": "AAPL", "horizon": "6m"},
            {"mode": "rolling", "ticker": "RELIANCE.NS", "horizon": "3m", "lookback": "1y",
             "drift": "risk_free", "n_windows": 20},
        ]},
    )

    mode: BacktestMode = Field(..., description=(
        "single: one past start date (needs start_date). rolling: up to 40 evenly spaced past "
        "start dates with band coverage and a calibration histogram."))
    ticker: str = Field(..., description="Stock symbol, e.g. AAPL or RELIANCE.NS / TCS.BO")
    horizon: str = Field(..., description="Forecast horizon, e.g. 1m, 3m, 6m, 1y (max 5y)")
    lookback: Lookback = Field("2y", description="History window before each start date")
    start_date: date | None = Field(None, description=(
        "single only: the forecast start (YYYY-MM-DD). The last close on or before it is used; "
        "it needs a full horizon of prices after it."))
    n_sims: int | None = Field(None, ge=MIN_SIMS, le=MAX_SIMS, description=(
        f"Simulated paths per start date (default {10_000} for single, "
        f"{DEFAULT_ROLLING_SIMS} for rolling)"))
    n_windows: int | None = Field(None, ge=MIN_WINDOWS, le=MAX_WINDOWS, description=(
        f"rolling only: number of start dates (default {DEFAULT_WINDOWS})"))
    seed: int = Field(42, ge=0, description="Random seed (non-negative integer)")
    drift: Drift = Field("historical", description=(
        "historical: drift from the lookback before each start date. risk_free: drift = "
        "today's risk-free rate (historical T-bill rates are not fetched)."))
    risk_free_rate: float | None = Field(
        None, ge=MIN_RATE, le=MAX_RATE, allow_inf_nan=False,
        description="Annual decimal (0.045 = 4.5%), only with drift=risk_free. Default: "
                    "today's per-currency default.")

    @field_validator("ticker")
    @classmethod
    def _check_ticker(cls, v: str) -> str:
        return validate_ticker(v)

    @field_validator("horizon")
    @classmethod
    def _check_horizon(cls, v: str) -> str:
        return validate_horizon(v)

    @field_validator("start_date")
    @classmethod
    def _check_start(cls, v: date | None) -> date | None:
        if v is None:
            return v
        if v < MIN_START_DATE:
            raise ValueError(f"start_date must be on or after {MIN_START_DATE.isoformat()}")
        if v > date.today():
            raise ValueError("start_date must not be in the future")
        return v

    @model_validator(mode="after")
    def _check_mode_fields(self) -> "BacktestRequest":
        if self.risk_free_rate is not None and self.drift != "risk_free":
            raise ValueError("risk_free_rate can only be set when drift is 'risk_free'")
        if self.mode == "single":
            if self.start_date is None:
                raise ValueError("start_date is required when mode is 'single'")
            if self.n_windows is not None:
                raise ValueError("n_windows only applies when mode is 'rolling'")
        elif self.start_date is not None:
            raise ValueError("start_date only applies when mode is 'single'")
        return self

    @property
    def sims(self) -> int:
        return self.n_sims or (10_000 if self.mode == "single" else DEFAULT_ROLLING_SIMS)

    @property
    def windows(self) -> int:
        return self.n_windows or DEFAULT_WINDOWS


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class FinalPriceStats(BaseModel):
    mean: float
    median: float
    p5: float
    p25: float
    p75: float
    p95: float
    min: float
    max: float


class Histogram(BaseModel):
    bin_edges: list[float]
    counts: list[int]


class Analysis(BaseModel):
    final_price: FinalPriceStats
    expected_return_pct: float
    prob_below_start: float
    var_95_pct: float
    histogram: Histogram
    days: list[int] = Field(..., description="Trading-day index (0 = last close) of each point")
    mean_path: list[float]
    bands: dict[str, list[float]] = Field(..., description="Percentile bands p5, p25, p50, p75, p95")
    sample_paths: list[list[float]]
    sample_path_indices: list[int]


class SimulateResponse(BaseModel):
    metadata: dict[str, Any]
    parameters: dict[str, Any]
    settings: dict[str, Any]
    analysis: Analysis


class SingleBacktestResult(BaseModel):
    start_date: str
    end_date: str
    lookback_start_date: str
    latest_start_date: str | None
    actual_path: list[float] = Field(..., description="Realised closes aligned with analysis.days")
    actual_final: float
    actual_return_pct: float
    percentile_rank: float = Field(..., description="% of simulated final prices below the actual one")
    inside_50: bool
    inside_90: bool


class SingleBacktestResponse(BaseModel):
    metadata: dict[str, Any]
    parameters: dict[str, Any]
    settings: dict[str, Any]
    analysis: Analysis
    backtest: SingleBacktestResult


class BacktestWindow(BaseModel):
    start_date: str
    end_date: str
    S0: float
    actual_final: float
    actual_return_pct: float
    mu: float
    mu_historical: float
    sigma: float
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float
    percentile_rank: float
    inside_50: bool
    inside_90: bool


class RollingSummary(BaseModel):
    n_windows: int
    first_start_date: str
    last_start_date: str
    coverage_50: float = Field(..., description="Share of windows inside the 25-75% band (ideal 0.5)")
    coverage_90: float = Field(..., description="Share of windows inside the 5-95% band (ideal 0.9)")
    below_p5: float
    above_p95: float
    mean_percentile_rank: float = Field(..., description="Ideal ~50")
    pit_histogram: Histogram = Field(..., description="10 bins of percentile rank (0-100)")


class RollingBacktestResponse(BaseModel):
    metadata: dict[str, Any]
    settings: dict[str, Any]
    summary: RollingSummary
    windows: list[BacktestWindow]
