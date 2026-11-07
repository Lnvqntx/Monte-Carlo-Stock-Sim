"""POST /api/backtest tests. The price fetch is mocked with synthetic prices; no network."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import core
from api import main as api_main
from api.serialize import MAX_POINTS, N_SAMPLE_PATHS, serialize_backtest
from core.backtest import BacktestDateError
from core.errors import DataFetchError, InsufficientDataError, InvalidTickerError
from tests.test_backtest import gbm_data


@pytest.fixture(scope="module")
def data():
    return gbm_data(n_days=252 * 12, ticker="AAPL")


@pytest.fixture
def client():
    api_main.app.state.cache.clear()
    with TestClient(api_main.app, raise_server_exceptions=False) as c:
        yield c
    api_main.app.state.cache.clear()


class FetchRecorder(list):
    """Calls made to the fake fetch; .set() changes what it returns or raises."""

    def __init__(self, value):
        super().__init__()
        self.value = value

    def set(self, value):
        self.value = value


@pytest.fixture
def mock_fetch(monkeypatch, data):
    """Serve synthetic history from core.backtest.fetch_price_history; records calls."""
    rec = FetchRecorder(data)

    def fake(ticker, start, end=None):
        rec.append(dict(ticker=ticker, start=start))
        if isinstance(rec.value, Exception):
            raise rec.value
        return rec.value

    monkeypatch.setattr("core.backtest.fetch_price_history", fake)
    return rec


def post(client, **body):
    return client.post("/api/backtest", json=body)


def assert_error(resp, status, code):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == code
    return body["error"]["message"]


# --- single ------------------------------------------------------------------------------

def test_single_returns_trimmed_result_with_actual_path(client, mock_fetch):
    resp = post(client, mode="single", ticker="aapl", horizon="1y", start_date="2024-01-02")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"metadata", "parameters", "settings", "analysis", "backtest"}
    a, bt = body["analysis"], body["backtest"]
    assert len(a["days"]) <= MAX_POINTS
    assert len(a["sample_paths"]) == N_SAMPLE_PATHS
    assert len(bt["actual_path"]) == len(a["days"])
    assert a["days"][0] == 0 and a["days"][-1] == 252
    assert bt["actual_path"][-1] == bt["actual_final"]
    assert bt["start_date"] == "2024-01-02"
    assert body["settings"]["mode"] == "single"
    assert body["settings"]["n_sims"] == 10_000
    assert mock_fetch[0]["ticker"] == "AAPL"


def test_single_5y_response_size_limits(client, mock_fetch):
    resp = post(client, mode="single", ticker="AAPL", horizon="5y", start_date="2018-06-01",
                lookback="1y", n_sims=2000)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["analysis"]["days"]) <= MAX_POINTS
    assert all(len(p) <= MAX_POINTS for p in body["analysis"]["sample_paths"])
    assert len(body["backtest"]["actual_path"]) <= MAX_POINTS
    assert len(resp.content) < 300_000


def test_single_requires_start_date(client, mock_fetch):
    msg = assert_error(post(client, mode="single", ticker="AAPL", horizon="6m"), 422,
                       "invalid_input")
    assert "start_date is required" in msg
    assert not mock_fetch


def test_single_rejects_future_and_bad_dates(client, mock_fetch):
    future = (date.today() + timedelta(days=5)).isoformat()
    msg = assert_error(post(client, mode="single", ticker="AAPL", horizon="6m",
                            start_date=future), 422, "invalid_input")
    assert "future" in msg
    assert_error(post(client, mode="single", ticker="AAPL", horizon="6m",
                      start_date="2025-13-01"), 422, "invalid_input")
    assert_error(post(client, mode="single", ticker="AAPL", horizon="6m",
                      start_date="1900-01-01"), 422, "invalid_input")
    assert not mock_fetch


def test_single_too_recent_is_invalid_input_with_latest_date(client, mock_fetch, data):
    msg = assert_error(post(client, mode="single", ticker="AAPL", horizon="6m",
                            start_date="2026-10-01"), 422, "invalid_input")
    assert data.prices.index[-127].date().isoformat() in msg


def test_single_not_enough_history(client, mock_fetch, data):
    early = (data.prices.index[0] + timedelta(days=60)).date().isoformat()
    msg = assert_error(post(client, mode="single", ticker="AAPL", horizon="6m",
                            start_date=early), 422, "insufficient_data")
    assert "backtest" in msg and "later start date" in msg


# --- rolling -----------------------------------------------------------------------------

def test_rolling_defaults_and_shape(client, mock_fetch):
    resp = post(client, mode="rolling", ticker="AAPL", horizon="6m")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"metadata", "settings", "summary", "windows"}
    assert body["settings"]["n_sims"] == 2000
    assert body["settings"]["n_windows_requested"] == 40
    assert len(body["windows"]) == body["summary"]["n_windows"] == 40
    assert set(body["windows"][0]) >= {"start_date", "S0", "actual_final", "p5", "p25", "p50",
                                       "p75", "p95", "percentile_rank", "inside_50",
                                       "inside_90"}
    assert len(body["summary"]["pit_histogram"]["counts"]) == 10
    assert len(resp.content) < 40_000


def test_rolling_risk_free_note(client, mock_fetch):
    body = post(client, mode="rolling", ticker="AAPL", horizon="3m", drift="risk_free",
                risk_free_rate=0.045, n_windows=10).json()
    assert body["settings"]["risk_free_rate"] == 0.045
    assert "Your rate" in body["settings"]["rate_note"]
    assert all(w["mu"] == 0.045 for w in body["windows"])


@pytest.mark.parametrize("body, needle", [
    ({"n_windows": 41}, "n_windows"),
    ({"n_windows": 2}, "n_windows"),
    ({"start_date": "2024-01-02"}, "start_date only applies"),
    ({"n_sims": 50_000}, "n_sims"),
    ({"risk_free_rate": 0.04}, "risk_free_rate"),
    ({"horizon": "6y"}, "horizon"),
    ({"lookback": "3y"}, "lookback"),
    ({"mode": "both"}, "mode"),
    ({"ticker": "AA PL"}, "ticker"),
])
def test_rolling_invalid_input(client, mock_fetch, body, needle):
    req = {"mode": "rolling", "ticker": "AAPL", "horizon": "6m", **body}
    msg = assert_error(client.post("/api/backtest", json=req), 422, "invalid_input")
    assert needle in msg
    assert not mock_fetch


def test_single_rejects_n_windows(client, mock_fetch):
    msg = assert_error(post(client, mode="single", ticker="AAPL", horizon="6m",
                            start_date="2024-01-02", n_windows=10), 422, "invalid_input")
    assert "n_windows" in msg


def test_rolling_not_enough_history(client, mock_fetch):
    mock_fetch.set(gbm_data(n_days=400))
    msg = assert_error(post(client, mode="rolling", ticker="AAPL", horizon="1y"), 422,
                       "insufficient_data")
    assert "shorter lookback or horizon" in msg


@pytest.mark.parametrize("exc, status, code", [
    (InvalidTickerError("x"), 404, "invalid_ticker"),
    (DataFetchError("x"), 502, "data_unavailable"),
    (InsufficientDataError("x"), 422, "insufficient_data"),
    (RuntimeError("secret"), 500, "internal_error"),
])
def test_core_errors_map_to_error_shape(client, mock_fetch, exc, status, code):
    mock_fetch.set(exc)
    resp = post(client, mode="rolling", ticker="AAPL", horizon="6m")
    msg = assert_error(resp, status, code)
    assert "secret" not in msg and "Traceback" not in resp.text


def test_date_error_maps_to_invalid_input(client, monkeypatch):
    def boom(*a, **k):
        raise BacktestDateError("Start date is too recent")

    monkeypatch.setattr(core, "single_backtest", boom)
    msg = assert_error(post(client, mode="single", ticker="AAPL", horizon="6m",
                            start_date="2024-01-02"), 422, "invalid_input")
    assert msg == "Start date is too recent"


# --- caching -----------------------------------------------------------------------------

def test_backtests_are_cached_by_all_inputs(client, mock_fetch):
    base = dict(mode="rolling", ticker="AAPL", horizon="6m", n_windows=10)
    first = post(client, **base).json()
    assert post(client, **base).json() == first
    assert len(mock_fetch) == 1
    post(client, **base, seed=7)
    post(client, **base, drift="risk_free")
    post(client, mode="single", ticker="AAPL", horizon="6m", start_date="2024-01-02")
    post(client, mode="single", ticker="AAPL", horizon="6m", start_date="2024-01-03")
    assert len(mock_fetch) == 5


def test_backtest_and_simulate_cache_keys_do_not_collide():
    from api.schemas import BacktestRequest, SimulateRequest

    sim = api_main.cache_key(SimulateRequest(ticker="AAPL", horizon="6m"))
    bt = api_main.backtest_cache_key(BacktestRequest(mode="rolling", ticker="AAPL",
                                                     horizon="6m"))
    assert sim != bt and bt[0] == "backtest"


def test_errors_are_not_cached(client, mock_fetch, data):
    mock_fetch.set(DataFetchError("down"))
    assert post(client, mode="rolling", ticker="AAPL", horizon="6m").status_code == 502
    mock_fetch.set(data)
    assert post(client, mode="rolling", ticker="AAPL", horizon="6m").status_code == 200


def test_serialize_backtest_passes_rolling_through(data):
    roll = core.rolling_backtest_from_prices(data, "6m", n_windows=5, n_sims=200)
    assert serialize_backtest(roll) is roll
    json.dumps(serialize_backtest(
        core.single_backtest_from_prices(data, "2024-01-02", "6m", n_sims=500)))


def test_openapi_lists_backtest(client):
    spec = client.get("/openapi.json").json()
    assert "/api/backtest" in spec["paths"]
