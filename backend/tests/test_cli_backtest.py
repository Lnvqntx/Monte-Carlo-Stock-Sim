"""CLI --backtest tests. The history fetch is mocked with synthetic prices; no network."""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")

import pytest

import cli
import core
from core.errors import DataFetchError, InvalidTickerError
from tests.test_backtest import gbm_data


@pytest.fixture(scope="module")
def data():
    return gbm_data(ticker="AAPL")


@pytest.fixture
def mock_fetch(monkeypatch, data):
    calls: list[str] = []

    def install(outcome=data):
        def fake(ticker, start, end=None):
            calls.append(ticker)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr("core.backtest.fetch_price_history", fake)
        return calls

    return install


def run(tmp_path, *args):
    return cli.main(["--save", str(tmp_path / "out"), "--no-show", *args])


def test_single_backtest_prints_verdict_and_saves_chart(mock_fetch, tmp_path, capsys):
    calls = mock_fetch()
    code = run(tmp_path, "--ticker", "aapl", "--horizon", "6m", "--backtest", "2025-05-01",
               "--sims", "2000")
    out = capsys.readouterr().out
    assert code == 0, out
    assert calls == ["AAPL"]
    assert "What actually happened" in out
    assert "Percentile in forecast" in out
    assert "50% band" in out and "90% band" in out
    assert "no look-ahead" in out.replace("\n", " ")
    assert (tmp_path / "out" / "AAPL_6m_backtest_2025-05-01.png").stat().st_size > 10_000


def test_rolling_backtest_table_and_calibration_chart(mock_fetch, tmp_path, capsys):
    mock_fetch()
    code = run(tmp_path, "--ticker", "AAPL", "--horizon", "6m", "--backtest", "rolling",
               "--windows", "10", "--json", str(tmp_path / "roll.json"))
    out = capsys.readouterr().out
    assert code == 0, out
    assert "Inside 90% band" in out and "Inside 50% band" in out
    assert "Mean percentile rank" in out
    assert "2,000 sims each" in out  # rolling default
    saved = json.loads((tmp_path / "roll.json").read_text())
    assert saved["summary"]["n_windows"] == 10
    assert (tmp_path / "out" / "AAPL_6m_calibration.png").stat().st_size > 10_000


def test_rolling_risk_free_prints_rate_note(mock_fetch, tmp_path, capsys):
    mock_fetch()
    assert run(tmp_path, "--ticker", "AAPL", "--horizon", "3m", "--backtest", "rolling",
               "--windows", "5", "--drift", "risk_free") == 0
    assert "historical rates are not fetched" in capsys.readouterr().out.replace("\n", " ")


@pytest.mark.parametrize("args, expected", [
    (["--backtest", "someday"], "--backtest must be 'rolling' or a date"),
    (["--backtest", "2026-10-01"], "too recent"),
    (["--backtest", "2017-01-02"], "Not enough price history"),
    (["--backtest", "rolling", "--windows", "41"], "--windows must be between"),
    (["--backtest", "rolling", "--rate", "0.04"], "--rate only applies"),
])
def test_backtest_input_errors(mock_fetch, tmp_path, capsys, args, expected):
    mock_fetch()
    code = run(tmp_path, "--ticker", "AAPL", "--horizon", "6m", *args)
    err = capsys.readouterr().err.replace("\n", " ")
    assert code == cli.EXIT_ERROR
    assert expected in err


@pytest.mark.parametrize("exc, expected", [
    (InvalidTickerError("x"), "No data found"),
    (DataFetchError("x"), "Could not download"),
])
def test_backtest_fetch_errors(mock_fetch, tmp_path, capsys, exc, expected):
    mock_fetch(exc)
    assert run(tmp_path, "--ticker", "AAPL", "--horizon", "6m", "--backtest", "rolling") == 1
    assert expected in capsys.readouterr().err


def test_backtest_does_not_call_run_simulation(mock_fetch, tmp_path, monkeypatch):
    mock_fetch()
    monkeypatch.setattr(core, "run_simulation", lambda *a, **k: pytest.fail("not a forecast"))
    assert run(tmp_path, "--ticker", "AAPL", "--horizon", "1m", "--backtest", "rolling",
               "--windows", "5") == 0
