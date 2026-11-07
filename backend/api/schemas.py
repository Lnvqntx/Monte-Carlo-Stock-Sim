"""Pydantic request/response models for the HTTP API."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core import TRADING_DAYS_PER_YEAR, parse_horizon

MAX_HORIZON_YEARS = 5
MAX_HORIZON_DAYS = MAX_HORIZON_YEARS * TRADING_DAYS_PER_YEAR
MIN_SIMS = 1_000
MAX_SIMS = 20_000
TICKER_RE = re.compile(r"^[A-Z0-9.\-^=]{1,20}$")

Lookback = Literal["6mo", "1y", "2y", "5y"]


class SimulateRequest(BaseModel):
    """Body of POST /api/simulate."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"ticker": "AAPL", "horizon": "6m"},
                                        {"ticker": "RELIANCE.NS", "horizon": "1y",
                                         "lookback": "5y", "n_sims": 5000, "seed": 7}]},
    )

    ticker: str = Field(..., description="Stock symbol, e.g. AAPL or RELIANCE.NS / TCS.BO")
    horizon: str = Field(..., description="Forecast horizon, e.g. 1w, 3m, 6m, 1y (max 5y)")
    lookback: Lookback = Field("2y", description="History window used to estimate parameters")
    n_sims: int = Field(10_000, ge=MIN_SIMS, le=MAX_SIMS, description="Number of simulated paths")
    seed: int = Field(42, ge=0, description="Random seed (non-negative integer)")

    @field_validator("ticker")
    @classmethod
    def _check_ticker(cls, v: str) -> str:
        symbol = v.strip().upper()
        if not symbol:
            raise ValueError("ticker must not be empty")
        if len(symbol) > 20:
            raise ValueError("ticker must be at most 20 characters")
        if not TICKER_RE.match(symbol):
            raise ValueError("ticker may only contain letters, digits and . - ^ =")
        return symbol

    @field_validator("horizon")
    @classmethod
    def _check_horizon(cls, v: str) -> str:
        h = parse_horizon(v)  # raises ValueError with a readable message
        if h.n_days > MAX_HORIZON_DAYS:
            raise ValueError(f"horizon must be at most {MAX_HORIZON_YEARS}y, got {h.label!r}")
        return h.label


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
