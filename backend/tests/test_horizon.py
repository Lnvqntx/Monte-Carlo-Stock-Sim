import pytest

from core.horizon import parse_horizon


@pytest.mark.parametrize(
    "text, days",
    [("1w", 5), ("2w", 10), ("1m", 21), ("3m", 63), ("6m", 126), ("1y", 252),
     ("2y", 504), ("10d", 10), (" 3M ", 63), ("1Y", 252)],
)
def test_valid(text, days):
    h = parse_horizon(text)
    assert h.n_days == days
    assert h.T == pytest.approx(days / 252)


def test_six_months_is_half_year():
    assert parse_horizon("6m").T == pytest.approx(0.5)


@pytest.mark.parametrize("text", ["", "abc", "0m", "0y", "-1m", "1.5y", "3x", "m3", "3 months", None, 5])
def test_invalid(text):
    with pytest.raises(ValueError):
        parse_horizon(text)
