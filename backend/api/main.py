"""FastAPI app exposing core.run_simulation over HTTP.

Run from backend/:
    uvicorn api.main:app --reload
Then open http://127.0.0.1:8000/docs

Environment variables:
    ALLOWED_ORIGINS     comma-separated CORS origins (default: http://localhost:3000)
    CACHE_TTL_SECONDS   result cache lifetime in seconds (default: 900; 0 disables caching)
    CACHE_MAX_ENTRIES   maximum cached results (default: 100)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import core
from core.errors import DataFetchError, InsufficientDataError, InvalidTickerError

from .cache import DEFAULT_MAX_ENTRIES, TTLCache, ttl_from_env
from .schemas import ErrorResponse, HealthResponse, SimulateRequest, SimulateResponse
from .serialize import serialize_result

logger = logging.getLogger("api")

DEFAULT_ORIGINS = "http://localhost:3000"

INVALID_TICKER_MESSAGE = (
    "No price data found for {ticker}. Check the symbol; for Indian stocks add .NS (NSE) "
    "or .BO (BSE), e.g. RELIANCE.NS. This can also be a temporary data issue, so try again "
    "shortly if the symbol is correct."
)
DATA_UNAVAILABLE_MESSAGE = "The market data provider is unavailable. Try again shortly."
INTERNAL_ERROR_MESSAGE = "Something went wrong while running the simulation."


class APIError(Exception):
    """An error rendered as {"error": {"code": ..., "message": ...}}."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code, self.code, self.message = status_code, code, message


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code,
                        content={"error": {"code": code, "message": message}})


def allowed_origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGINS") or DEFAULT_ORIGINS
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def _max_entries() -> int:
    try:
        return int(os.environ.get("CACHE_MAX_ENTRIES", DEFAULT_MAX_ENTRIES))
    except ValueError:
        return DEFAULT_MAX_ENTRIES


def format_validation_errors(errors: list[dict[str, Any]]) -> str:
    """Turn Pydantic's error list into one readable sentence."""
    parts = []
    for err in errors:
        loc = [str(p) for p in err.get("loc", ()) if p != "body"]
        field = ".".join(loc)
        kind, msg = err.get("type", ""), str(err.get("msg", "Invalid value"))
        msg = msg.removeprefix("Value error, ")
        if kind == "missing":
            parts.append(f"{field} is required" if field else "Request body is required")
        elif kind == "json_invalid":
            parts.append("Request body is not valid JSON")
        elif kind in ("model_attributes_type", "dict_type") and not field:
            parts.append("Request body must be a JSON object")
        else:
            parts.append(f"{field}: {msg}" if field else msg)
    return "; ".join(dict.fromkeys(parts)) or "Invalid input"


def _run_trimmed(req: SimulateRequest) -> dict[str, Any]:
    """Run the core simulation and trim it, mapping core errors to APIError."""
    try:
        result = core.run_simulation(req.ticker, req.horizon, lookback=req.lookback,
                                     n_sims=req.n_sims, seed=req.seed)
        return serialize_result(result)
    except InvalidTickerError:
        raise APIError(404, "invalid_ticker", INVALID_TICKER_MESSAGE.format(ticker=req.ticker))
    except InsufficientDataError as exc:
        raise APIError(422, "insufficient_data",
                       f"Not enough price history for {req.ticker} to simulate: {exc}. "
                       "Try a longer lookback.")
    except DataFetchError as exc:
        logger.warning("Data fetch failed for %s: %s", req.ticker, exc)
        raise APIError(502, "data_unavailable", DATA_UNAVAILABLE_MESSAGE)
    except Exception:
        logger.exception("Unexpected error simulating %s", req.ticker)
        raise APIError(500, "internal_error", INTERNAL_ERROR_MESSAGE)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Monte Carlo Stock Simulator API",
        version="0.1.0",
        description="GBM Monte Carlo simulation of stock prices. Model output, not financial advice.",
    )
    app.state.cache = TTLCache(ttl=ttl_from_env(), max_entries=_max_entries())

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "invalid_input",
                              format_validation_errors(jsonable_encoder(exc.errors())))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {404: "not_found", 405: "method_not_allowed"}
        return error_response(exc.status_code, codes.get(exc.status_code, "http_error"),
                              str(exc.detail))

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return error_response(500, "internal_error", INTERNAL_ERROR_MESSAGE)

    error_docs = {
        404: {"model": ErrorResponse, "description": "Unknown ticker (invalid_ticker)"},
        422: {"model": ErrorResponse,
              "description": "Invalid input (invalid_input) or too little history (insufficient_data)"},
        500: {"model": ErrorResponse, "description": "Unexpected error (internal_error)"},
        502: {"model": ErrorResponse, "description": "Data provider unavailable (data_unavailable)"},
    }

    @app.get("/api/health", response_model=HealthResponse, tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Sync endpoint: FastAPI runs it in a threadpool, so the blocking fetch/simulation
    # doesn't stall the event loop.
    @app.post("/api/simulate", response_model=SimulateResponse, responses=error_docs,
              tags=["simulation"])
    def simulate(req: SimulateRequest, request: Request) -> dict[str, Any]:
        cache: TTLCache = request.app.state.cache
        key = (req.ticker, req.horizon, req.lookback, req.n_sims, req.seed)
        cached = cache.get(key)
        if cached is not None:
            return cached
        # Cache the trimmed payload: same content the client gets, far less memory.
        payload = _run_trimmed(req)
        cache.set(key, payload)
        return payload

    return app


app = create_app()
