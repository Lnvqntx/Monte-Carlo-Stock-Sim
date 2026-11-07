"""CLI tests. core.run_simulation is mocked, so no network is used."""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")

import pytest

import cli
import core
from core import analyze, simulate_gbm
from core.errors import DataFetchError, InsufficientDataError, InvalidTickerError


def make_result(ticker="AAPL", currency="USD", horizon="6m", n_days=126, mu=0.12,
                sigma=0.25, S0=200.0, n_sims=2000, seed=42, long_name="Apple Inc."):
    """A realistic run_simulation-shaped result built from the real core maths."""
    paths = simulate_gbm(S0, mu, sigma, n_days / 252, n_days, n_sims, seed)
    return {
        "metadata": {"ticker": ticker, "currency": currency, "long_name": long_name,
                     "last_date": "2026-11-06", "n_prices": 503},
        "parameters": {"S0": S0, "mu": mu, "sigma": sigma, "n_returns": 502},
        "settings": {"horizon": horizon, "n_steps": n_days, "T_years": n_days / 252,
                     "lookback": "2y", "n_sims": n_sims, "seed": seed,
                     "trading_days_per_year": 252, "drift": "historical"},
        "analysis": analyze(paths, S0, seed=seed),
    }


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


def run(tmp_path, *args):
    return cli.main(["--save", str(tmp_path / "out"), "--no-show", *args])


def test_normal_run_prints_key_numbers(mock_run, tmp_path, capsys):
    result = make_result()
    calls = mock_run(result)
    code = run(tmp_path, "--ticker", "aapl", "--horizon", "6m")
    out = capsys.readouterr().out

    assert code == 0
    assert calls == [dict(ticker="AAPL", horizon="6m", lookback="2y", n_sims=10_000, seed=42,
                      drift="historical", risk_free_rate=None)]
    final = result["analysis"]["final_price"]
    assert "Apple Inc." in out and "AAPL" in out and "2026-11-06" in out
    assert "$200.00" in out
    assert "12.00%" in out and "25.00%" in out  # mu, sigma
    for key in ("mean", "median", "p5", "p25", "p75", "p95"):
        assert f"${final[key]:,.2f}" in out
    assert f"{result['analysis']['expected_return_pct']:+.2f}%" in out
    assert f"{result['analysis']['prob_below_start'] * 100:.1f}%" in out
    assert "financial advice" in out


def test_options_passed_through(mock_run, tmp_path):
    calls = mock_run(make_result())
    assert run(tmp_path, "--ticker", "AAPL", "--horizon", "1y", "--lookback", "5y",
               "--sims", "500", "--seed", "7") == 0
    assert calls == [dict(ticker="AAPL", horizon="1y", lookback="5y", n_sims=500, seed=7,
                      drift="historical", risk_free_rate=None)]


def test_inr_currency_symbol(mock_run, tmp_path, capsys):
    mock_run(make_result(ticker="RELIANCE.NS", currency="INR", S0=2900.0))
    assert run(tmp_path, "--ticker", "RELIANCE.NS", "--horizon", "6m") == 0
    assert "₹2,900.00" in capsys.readouterr().out


def test_other_currency_uses_code(mock_run, tmp_path, capsys):
    mock_run(make_result(ticker="SAP.DE", currency="EUR", S0=150.0))
    assert run(tmp_path, "--ticker", "SAP.DE", "--horizon", "6m") == 0
    assert "EUR 150.00" in capsys.readouterr().out


def test_var_positive_shows_loss(mock_run, tmp_path, capsys):
    result = make_result()
    mock_run(result)
    run(tmp_path, "--ticker", "AAPL", "--horizon", "6m")
    var_pct = result["analysis"]["var_95_pct"]
    assert var_pct > 0
    out = capsys.readouterr().out
    assert f"${200.0 * var_pct / 100:,.2f}" in out
    assert "No loss at 95% confidence" not in out


def test_negative_var_shows_no_loss(mock_run, tmp_path, capsys):
    result = make_result(mu=3.0, sigma=0.05)  # strong drift, tiny vol -> p5 above S0
    assert result["analysis"]["var_95_pct"] < 0
    mock_run(result)
    assert run(tmp_path, "--ticker", "AAPL", "--horizon", "6m") == 0
    assert "No loss at 95% confidence" in capsys.readouterr().out


@pytest.mark.parametrize(
    "exc, expected",
    [
        (InvalidTickerError("no data"), ["No data found for FAKE", ".NS or .BO",
                                         "RELIANCE.NS", "network"]),
        (InsufficientDataError("Only 10 trading days"), ["Not enough price history for FAKE",
                                                          "--lookback"]),
        (DataFetchError("boom"), ["Could not download data for FAKE", "internet connection"]),
        (ValueError("Invalid horizon 'xyz'"), ["Invalid input", "Invalid horizon", "1w, 3m"]),
    ],
)
def test_errors_exit_nonzero_with_message(mock_run, tmp_path, capsys, exc, expected):
    mock_run(exc)
    code = run(tmp_path, "--ticker", "fake", "--horizon", "xyz")
    captured = capsys.readouterr()
    assert code != 0
    err = " ".join(captured.err.split())  # undo rich line wrapping
    for text in expected:
        assert text in err
    assert "Traceback" not in captured.err + captured.out
    assert not (tmp_path / "out").exists()


def test_bad_sims_rejected(mock_run, tmp_path, capsys):
    calls = mock_run(make_result())
    assert run(tmp_path, "--ticker", "AAPL", "--horizon", "6m", "--sims", "0") != 0
    assert calls == []
    assert "--sims" in capsys.readouterr().err


def test_missing_required_args_exit_nonzero(capsys):
    with pytest.raises(SystemExit) as info:
        cli.main(["--ticker", "AAPL"])
    assert info.value.code != 0


def test_json_written_and_valid(mock_run, tmp_path):
    result = make_result()
    mock_run(result)
    json_path = tmp_path / "nested" / "result.json"
    assert run(tmp_path, "--ticker", "AAPL", "--horizon", "6m", "--json", str(json_path)) == 0
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded == json.loads(json.dumps(result))


def test_save_creates_both_pngs(mock_run, tmp_path):
    mock_run(make_result(ticker="RELIANCE.NS", currency="INR", horizon="3m", n_days=63))
    out_dir = tmp_path / "out"
    assert run(tmp_path, "--ticker", "RELIANCE.NS", "--horizon", "3m") == 0
    for name in ("RELIANCE.NS_3m_paths.png", "RELIANCE.NS_3m_hist.png"):
        png = out_dir / name
        assert png.exists() and png.stat().st_size > 1000
        assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_main_calls_only_run_simulation_for_numbers(mock_run, tmp_path, monkeypatch):
    mock_run(make_result())
    for name in ("fetch_prices", "estimate_parameters", "simulate_gbm", "analyze"):
        monkeypatch.setattr(core, name, lambda *a, _n=name, **k: pytest.fail(f"cli called core.{_n}"))
    assert run(tmp_path, "--ticker", "AAPL", "--horizon", "6m") == 0


# --- drift options --------------------------------------------------------------

def make_rf_result(rate=0.0412, source="live ^IRX"):
    result = make_result(mu=rate)
    result["parameters"]["mu_historical"] = 0.31
    result["settings"].update(drift="risk_free", risk_free_rate=rate, rate_source=source)
    return result


def test_drift_and_rate_passed_through(mock_run, tmp_path):
    calls = mock_run(make_rf_result(0.045, "user override"))
    assert run(tmp_path, "--ticker", "AAPL", "--horizon", "1y", "--drift", "risk_free",
               "--rate", "0.045") == 0
    assert calls[0]["drift"] == "risk_free" and calls[0]["risk_free_rate"] == 0.045


def test_risk_free_summary_shows_model_rate_and_historical_mu(mock_run, tmp_path, capsys):
    mock_run(make_rf_result())
    assert run(tmp_path, "--ticker", "AAPL", "--horizon", "6m", "--drift", "risk_free") == 0
    out = capsys.readouterr().out
    assert "Risk-free (risk-neutral)" in out
    assert "4.12% (live ^IRX)" in out
    assert "31.00%" in out  # historical mu shown for comparison
    assert "not a forecast" in out


def test_historical_summary_shows_model(mock_run, tmp_path, capsys):
    mock_run(make_result())
    assert run(tmp_path, "--ticker", "AAPL", "--horizon", "6m") == 0
    out = capsys.readouterr().out
    assert "Historical" in out and "Risk-free rate" not in out


@pytest.mark.parametrize("args,expected", [
    (["--rate", "0.04"], "only applies with --drift risk_free"),
    (["--drift", "risk_free", "--rate", "4.5"], "between -0.05 and 0.25"),
    (["--drift", "risk_free", "--rate", "-0.1"], "between -0.05 and 0.25"),
])
def test_bad_rate_rejected(mock_run, tmp_path, capsys, args, expected):
    calls = mock_run(make_result())
    assert run(tmp_path, "--ticker", "AAPL", "--horizon", "6m", *args) == 1
    assert expected in capsys.readouterr().err
    assert calls == []


def test_bad_drift_choice_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--ticker", "AAPL", "--horizon", "6m", "--drift", "neutral"])
    assert exc.value.code == 2
