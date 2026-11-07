import json

import pytest

from core.analyze import analyze
from core.simulate import simulate_gbm

S0 = 100.0


@pytest.fixture(scope="module")
def result():
    paths = simulate_gbm(S0, 0.08, 0.25, 1.0, 252, 10_000, seed=42)
    return paths, analyze(paths, S0)


def test_required_keys(result):
    _, r = result
    for key in ["final_price", "expected_return_pct", "prob_below_start", "var_95_pct",
                "bands", "mean_path", "sample_paths", "histogram"]:
        assert key in r
    assert set(r["final_price"]) == {"mean", "median", "p5", "p25", "p75", "p95", "min", "max"}
    assert set(r["bands"]) == {"p5", "p25", "p50", "p75", "p95"}
    assert set(r["histogram"]) == {"bin_edges", "counts"}


def test_percentiles_ordered(result):
    _, r = result
    f = r["final_price"]
    assert f["min"] <= f["p5"] <= f["p25"] <= f["median"] <= f["p75"] <= f["p95"] <= f["max"]
    b = r["bands"]
    for t in range(len(b["p5"])):
        assert b["p5"][t] <= b["p25"][t] <= b["p50"][t] <= b["p75"][t] <= b["p95"][t]


def test_probabilities_and_lengths(result):
    paths, r = result
    assert 0.0 <= r["prob_below_start"] <= 1.0
    n_points = paths.shape[1]
    assert len(r["mean_path"]) == n_points
    assert all(len(v) == n_points for v in r["bands"].values())
    assert len(r["sample_paths"]) == 100
    assert all(len(p) == n_points for p in r["sample_paths"])
    assert len(r["histogram"]["counts"]) == 50
    assert len(r["histogram"]["bin_edges"]) == 51
    assert sum(r["histogram"]["counts"]) == paths.shape[0]
    assert r["var_95_pct"] == pytest.approx((S0 - r["final_price"]["p5"]) / S0 * 100, abs=1e-3)


def test_json_serializable_plain_types(result):
    _, r = result
    s = json.dumps(r)
    assert json.loads(s) == r


def test_sample_paths_deterministic():
    paths = simulate_gbm(S0, 0.08, 0.25, 0.25, 63, 2000, seed=1)
    assert analyze(paths, S0)["sample_path_indices"] == analyze(paths, S0)["sample_path_indices"]
    small = analyze(paths[:30], S0)
    assert len(small["sample_paths"]) == 30
