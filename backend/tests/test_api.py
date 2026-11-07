"""API tests. core.run_simulation is mocked, so no network is used."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import core
from api import main as api_main
from api.cache import TTLCache, ttl_from_env
from api.serialize import MAX_POINTS, N_SAMPLE_PATHS, downsample_indices, serialize_result
from core import analyze, parse_horizon, simulate_gbm
from core.errors import DataFetchError, InsufficientDataError, InvalidTickerError

SERIES_KEYS = ("mean_path",)
BAND_KEYS = ("p5", "p25", "p50", "p75", "p95")


def make_result(horizon="6m", ticker="AAPL", S0=200.0, mu=0.12, sigma=0.25, n_sims=2000,
                seed=42):
    """A realistic run_simulation-shaped result built from the real core maths."""
    h = parse_horizon(horizon)
    paths = simulate_gbm(S0, mu, sigma, h.T, h.n_days, n_sims, seed)
    return {
        "metadata": {"ticker": ticker, "currency": "USD", "long_name": "Apple Inc.",
                     "last_date": "2026-11-06", "n_prices": 503},
        "parameters": {"S0": S0, "mu": mu, "sigma": sigma, "n_returns": 502},
        "settings": {"horizon": h.label, "n_steps": h.n_days, "T_years": round(h.T, 6),
                     "lookback": "2y", "n_sims": n_sims, "seed": seed,
                     "trading_days_per_year": 252, "drift": "historical"},
        "analysis": analyze(paths, S0, seed=seed),
    }


@pytest.fixture(scope="module")
def result_6m():
    return make_result("6m")


@pytest.fixture(scope="module")
def result_5y():
    return make_result("5y")


@pytest.fixture
def client():
    api_main.app.state.cache.clear()
    with TestClient(api_main.app, raise_server_exceptions=False) as c:
        yield c
    api_main.app.state.cache.clear()


@pytest.fixture
def mock_run(monkeypatch):
    """Replace core.run_simulation; returns a setter taking a result or an exception."""
    calls: list[dict] = []

    def _install(outcome):
        def fake(ticker, horizon, lookback="2y", n_sims=10_000, seed=42, drift="historical",
                 risk_free_rate=None):
            calls.append(dict(ticker=ticker, horizon=horizon, lookback=lookback,
                              n_sims=n_sims, seed=seed, drift=drift,
                              risk_free_rate=risk_free_rate))
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr(core, "run_simulation", fake)
        return calls

    return _install


def assert_error(resp, status: int, code: str):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    return body["error"]["message"]


# --- health -----------------------------------------------------------------

def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root_lists_links(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "Monte Carlo Stock Simulator API"
    assert body["description"]
    assert body["links"] == {"docs": "/docs", "health": "/api/health",
                             "website": "https://monte-carlo-stock-sim.vercel.app"}
    assert client.get(body["links"]["docs"]).status_code == 200
    assert client.get(body["links"]["health"]).status_code == 200


# --- successful simulation ----------------------------------------------------

def test_simulate_returns_trimmed_result(client, mock_run, result_5y):
    calls = mock_run(result_5y)
    resp = client.post("/api/simulate", json={"ticker": " aapl ", "horizon": "5y"})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Request was normalised and defaults applied.
    assert calls == [dict(ticker="AAPL", horizon="5y", lookback="2y", n_sims=10_000, seed=42,
                      drift="historical", risk_free_rate=None)]

    assert set(body) == {"metadata", "parameters", "settings", "analysis"}
    a = body["analysis"]
    assert set(a) == {"final_price", "expected_return_pct", "prob_below_start", "var_95_pct",
                      "histogram", "days", "mean_path", "bands", "sample_paths",
                      "sample_path_indices"}

    full = result_5y["analysis"]
    n_full = len(full["mean_path"])  # 1261
    days = a["days"]
    assert 2 <= len(days) <= MAX_POINTS
    assert days[0] == 0 and days[-1] == n_full - 1
    assert days == sorted(set(days))

    assert len(a["mean_path"]) == len(days)
    assert a["mean_path"][0] == full["mean_path"][0]
    assert a["mean_path"][-1] == full["mean_path"][-1]
    assert a["mean_path"] == [full["mean_path"][d] for d in days]

    assert set(a["bands"]) == set(BAND_KEYS)
    for k in BAND_KEYS:
        assert len(a["bands"][k]) == len(days)
        assert a["bands"][k][0] == full["bands"][k][0]
        assert a["bands"][k][-1] == full["bands"][k][-1]

    assert len(a["sample_paths"]) == N_SAMPLE_PATHS == 50
    assert len(a["sample_path_indices"]) == 50
    assert set(a["sample_path_indices"]) <= set(full["sample_path_indices"])
    for p in a["sample_paths"]:
        assert len(p) == len(days)

    # Unchanged pass-through fields.
    for k in ("final_price", "expected_return_pct", "prob_below_start", "var_95_pct",
              "histogram"):
        assert a[k] == full[k]
    for k in ("metadata", "parameters", "settings"):
        assert body[k] == result_5y[k]


def test_short_horizon_keeps_every_point(client, mock_run):
    result = make_result("1w")
    mock_run(result)
    a = client.post("/api/simulate", json={"ticker": "AAPL", "horizon": "1w"}).json()["analysis"]
    assert a["days"] == list(range(6))
    assert a["mean_path"] == result["analysis"]["mean_path"]


def test_5y_response_under_300kb(client, mock_run, result_5y):
    mock_run(result_5y)
    resp = client.post("/api/simulate", json={"ticker": "AAPL", "horizon": "5y"})
    assert resp.status_code == 200
    assert len(resp.content) < 300 * 1024, f"{len(resp.content) / 1024:.1f} KB"


def test_indian_and_index_tickers_accepted(client, mock_run, result_6m):
    calls = mock_run(result_6m)
    for t in ("reliance.ns", "TCS.BO", "^GSPC", "EURUSD=X", "BRK-B"):
        assert client.post("/api/simulate", json={"ticker": t, "horizon": "6m"}).status_code == 200
    assert [c["ticker"] for c in calls] == ["RELIANCE.NS", "TCS.BO", "^GSPC", "EURUSD=X", "BRK-B"]


# --- core errors -> HTTP errors ------------------------------------------------

def test_invalid_ticker_404(client, mock_run):
    mock_run(InvalidTickerError("No price data found for ticker 'ZZZZ'"))
    msg = assert_error(client.post("/api/simulate", json={"ticker": "zzzz", "horizon": "6m"}),
                       404, "invalid_ticker")
    assert "ZZZZ" in msg and ".NS" in msg and ".BO" in msg and "temporary" in msg


def test_insufficient_data_422(client, mock_run):
    mock_run(InsufficientDataError("Only 20 trading days for NEWCO; need at least 60"))
    msg = assert_error(client.post("/api/simulate", json={"ticker": "NEWCO", "horizon": "6m"}),
                       422, "insufficient_data")
    assert "20 trading days" in msg


def test_data_fetch_error_502(client, mock_run):
    mock_run(DataFetchError("connection reset by peer"))
    msg = assert_error(client.post("/api/simulate", json={"ticker": "AAPL", "horizon": "6m"}),
                       502, "data_unavailable")
    assert msg == "The market data provider is unavailable. Try again shortly."


def test_unexpected_error_500_without_traceback(client, mock_run):
    mock_run(RuntimeError("secret internal detail"))
    resp = client.post("/api/simulate", json={"ticker": "AAPL", "horizon": "6m"})
    msg = assert_error(resp, 500, "internal_error")
    assert "secret" not in resp.text and "Traceback" not in resp.text
    assert "RuntimeError" not in msg


def test_errors_are_not_cached(client, mock_run):
    calls = mock_run(DataFetchError("down"))
    for _ in range(2):
        client.post("/api/simulate", json={"ticker": "AAPL", "horizon": "6m"})
    assert len(calls) == 2


# --- validation ---------------------------------------------------------------

@pytest.mark.parametrize("body, field", [
    ({"ticker": "AAPL", "horizon": "6 months"}, "horizon"),
    ({"ticker": "AAPL", "horizon": "0m"}, "horizon"),
    ({"ticker": "AAPL", "horizon": "6y"}, "horizon"),
    ({"ticker": "AAPL", "horizon": "61m"}, "horizon"),
    ({"ticker": "AAPL", "horizon": "1261d"}, "horizon"),
    ({"ticker": "AAPL", "horizon": "6m", "lookback": "3y"}, "lookback"),
    ({"ticker": "AAPL", "horizon": "6m", "lookback": "2Y"}, "lookback"),
    ({"ticker": "AAPL", "horizon": "6m", "n_sims": 999}, "n_sims"),
    ({"ticker": "AAPL", "horizon": "6m", "n_sims": 20001}, "n_sims"),
    ({"ticker": "AAPL", "horizon": "6m", "n_sims": 5000.5}, "n_sims"),
    ({"ticker": "AAPL", "horizon": "6m", "seed": "abc"}, "seed"),
    ({"ticker": "AAPL", "horizon": "6m", "seed": -1}, "seed"),
    ({"ticker": "AAP L", "horizon": "6m"}, "ticker"),
    ({"ticker": "AAPL;DROP", "horizon": "6m"}, "ticker"),
    ({"ticker": "<script>", "horizon": "6m"}, "ticker"),
    ({"ticker": "   ", "horizon": "6m"}, "ticker"),
    ({"ticker": "A" * 21, "horizon": "6m"}, "ticker"),
    ({"horizon": "6m"}, "ticker"),
    ({"ticker": "AAPL"}, "horizon"),
    ({"ticker": "AAPL", "horizon": "6m", "drift": "neutral"}, "drift"),
    ({"ticker": "AAPL", "horizon": "6m", "drift": "risk_free", "risk_free_rate": 0.2501},
     "risk_free_rate"),
    ({"ticker": "AAPL", "horizon": "6m", "drift": "risk_free", "risk_free_rate": -0.06},
     "risk_free_rate"),
    ({"ticker": "AAPL", "horizon": "6m", "drift": "risk_free", "risk_free_rate": "4%"},
     "risk_free_rate"),
    ({"ticker": "AAPL", "horizon": "6m", "risk_free_rate": 0.04}, "risk_free_rate"),
])
def test_invalid_input_422(client, mock_run, result_6m, body, field):
    calls = mock_run(result_6m)
    msg = assert_error(client.post("/api/simulate", json=body), 422, "invalid_input")
    assert msg.startswith(field)
    assert "[{" not in msg  # not the raw Pydantic error list
    assert calls == []


def test_horizon_messages_are_readable(client):
    msg = assert_error(client.post("/api/simulate", json={"ticker": "AAPL", "horizon": "10y"}),
                       422, "invalid_input")
    assert msg == "horizon: horizon must be at most 5y, got '10y'"
    msg = assert_error(client.post("/api/simulate", json={"ticker": "AAPL"}), 422, "invalid_input")
    assert msg == "horizon is required"


def test_five_years_is_allowed(client, mock_run, result_5y):
    mock_run(result_5y)
    for h in ("5y", "60m", "1260d"):
        assert client.post("/api/simulate", json={"ticker": "AAPL", "horizon": h}).status_code == 200


def test_malformed_json_422(client):
    resp = client.post("/api/simulate", content=b"{not json",
                       headers={"Content-Type": "application/json"})
    assert_error(resp, 422, "invalid_input")


def test_unknown_route_uses_error_shape(client):
    assert_error(client.get("/api/nope"), 404, "not_found")
    assert_error(client.get("/api/simulate"), 405, "method_not_allowed")


# --- caching ------------------------------------------------------------------

def test_second_identical_request_served_from_cache(client, mock_run, result_6m):
    calls = mock_run(result_6m)
    body = {"ticker": "AAPL", "horizon": "6m"}
    r1 = client.post("/api/simulate", json=body)
    r2 = client.post("/api/simulate", json={"ticker": "aapl", "horizon": "6M", "seed": 42})
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()
    assert len(calls) == 1

    client.post("/api/simulate", json={**body, "seed": 7})  # different key -> new call
    assert len(calls) == 2


def test_cache_expiry_and_eviction(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("api.cache.time.monotonic", lambda: now[0])
    c = TTLCache(ttl=10, max_entries=2)
    c.set("a", 1)
    assert c.get("a") == 1
    now[0] += 10
    assert c.get("a") is None

    c.set("a", 1); c.set("b", 2); c.get("a"); c.set("c", 3)  # "b" is least recently used
    assert c.get("b") is None and c.get("a") == 1 and c.get("c") == 3
    assert len(c) == 2


def test_cache_ttl_from_env(monkeypatch):
    monkeypatch.setenv("CACHE_TTL_SECONDS", "60")
    assert ttl_from_env() == 60
    monkeypatch.setenv("CACHE_TTL_SECONDS", "junk")
    assert ttl_from_env() == 900
    monkeypatch.delenv("CACHE_TTL_SECONDS")
    assert ttl_from_env() == 900
    disabled = TTLCache(ttl=0)
    disabled.set("k", 1)
    assert disabled.get("k") is None


# --- CORS ---------------------------------------------------------------------

def test_cors_allows_localhost_3000(client, mock_run, result_6m):
    mock_run(result_6m)
    origin = "http://localhost:3000"
    pre = client.options("/api/simulate", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})
    assert pre.status_code == 200
    assert pre.headers["access-control-allow-origin"] == origin

    resp = client.post("/api/simulate", json={"ticker": "AAPL", "horizon": "6m"},
                       headers={"Origin": origin})
    assert resp.headers["access-control-allow-origin"] == origin
    err = client.post("/api/simulate", json={"ticker": "AAPL"}, headers={"Origin": origin})
    assert err.headers["access-control-allow-origin"] == origin

    other = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_allowed_origins_from_env(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com/, http://localhost:3000")
    app = api_main.create_app()
    with TestClient(app) as c:
        resp = c.get("/api/health", headers={"Origin": "https://app.example.com"})
    assert resp.headers["access-control-allow-origin"] == "https://app.example.com"


# --- serialize unit tests ---------------------------------------------------

@pytest.mark.parametrize("n", [1, 2, 7, 200, 201, 253, 1261, 5041])
def test_downsample_indices(n):
    idx = downsample_indices(n)
    assert idx[0] == 0 and idx[-1] == n - 1
    assert len(idx) == min(n, MAX_POINTS)
    assert idx == sorted(set(idx))


def test_serialize_is_json_ready(result_6m):
    out = serialize_result(result_6m)
    json.dumps(out)
    assert result_6m["analysis"]["sample_paths"].__len__() == 100  # input untouched


# --- drift options --------------------------------------------------------------

def test_drift_defaults_to_historical(client, mock_run, result_6m):
    calls = mock_run(result_6m)
    assert client.post("/api/simulate", json={"ticker": "AAPL", "horizon": "6m"}).status_code == 200
    assert calls[0]["drift"] == "historical" and calls[0]["risk_free_rate"] is None


def test_risk_free_options_passed_through(client, mock_run, result_6m):
    calls = mock_run(result_6m)
    for body in ({"drift": "risk_free"}, {"drift": "risk_free", "risk_free_rate": 0.045},
                 {"drift": "risk_free", "risk_free_rate": -0.05},
                 {"drift": "risk_free", "risk_free_rate": 0.25}):
        resp = client.post("/api/simulate", json={"ticker": "AAPL", "horizon": "6m", **body})
        assert resp.status_code == 200, resp.text
    assert [(c["drift"], c["risk_free_rate"]) for c in calls] == [
        ("risk_free", None), ("risk_free", 0.045), ("risk_free", -0.05), ("risk_free", 0.25)]


def test_rate_without_risk_free_message(client):
    msg = assert_error(client.post("/api/simulate", json={
        "ticker": "AAPL", "horizon": "6m", "risk_free_rate": 0.04}), 422, "invalid_input")
    assert msg == "risk_free_rate can only be set when drift is 'risk_free'"


def test_cache_key_distinguishes_drift_and_rate(client, mock_run, result_6m):
    calls = mock_run(result_6m)
    base = {"ticker": "AAPL", "horizon": "6m"}
    bodies = [base, {**base, "drift": "historical"}, {**base, "drift": "risk_free"},
              {**base, "drift": "risk_free"}, {**base, "drift": "risk_free", "risk_free_rate": 0.04},
              {**base, "drift": "risk_free", "risk_free_rate": 0.04},
              {**base, "drift": "risk_free", "risk_free_rate": 0.05}]
    for b in bodies:
        assert client.post("/api/simulate", json=b).status_code == 200
    assert [(c["drift"], c["risk_free_rate"]) for c in calls] == [
        ("historical", None), ("risk_free", None), ("risk_free", 0.04), ("risk_free", 0.05)]


def test_cache_key_function():
    from api.schemas import SimulateRequest

    a = SimulateRequest(ticker="AAPL", horizon="6m")
    b = SimulateRequest(ticker="AAPL", horizon="6m", drift="risk_free")
    c = SimulateRequest(ticker="AAPL", horizon="6m", drift="risk_free", risk_free_rate=0.04)
    assert len({api_main.cache_key(r) for r in (a, b, c)}) == 3


def test_end_to_end_risk_free_through_real_core(client, monkeypatch):
    """Real run_simulation (fetch mocked): response carries both mus and the rate source."""
    from core.data import PriceData
    from tests.conftest import make_gbm_prices

    prices = make_gbm_prices(504, seed=9)
    monkeypatch.setattr(core, "fetch_prices", lambda t, lookback="2y": PriceData(
        prices, t, "USD", "Test", prices.index[-1].date().isoformat()))
    monkeypatch.setattr("core.rates.fetch_live_tbill_rate", lambda: 0.0375)
    body = client.post("/api/simulate", json={"ticker": "AAPL", "horizon": "6m", "n_sims": 1000,
                                              "drift": "risk_free"}).json()
    assert body["parameters"]["mu"] == 0.0375
    assert "mu_historical" in body["parameters"]
    assert body["settings"]["drift"] == "risk_free"
    assert body["settings"]["risk_free_rate"] == 0.0375
    assert body["settings"]["rate_source"] == "live ^IRX"
