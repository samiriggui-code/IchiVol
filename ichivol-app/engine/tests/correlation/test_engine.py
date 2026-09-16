from __future__ import annotations

import pytest

from app.correlation import engine as correlation_engine
from app.correlation.engine import compute_correlation_matrix
from app.indicators.ichimoku import Candle
from app.market_data.resolve import ProviderNotWiredError


def _candles(closes: list[float], *, start_time: int = 0, step: int = 3_600_000) -> list[Candle]:
    return [
        Candle(time=start_time + i * step, open=c, high=c, low=c, close=c, volume=1.0)
        for i, c in enumerate(closes)
    ]


def _fake_resolve_and_fetch(fixtures: dict[str, list[Candle]]):
    def _resolve(symbol: str, timeframe: str, limit: int = 300, **kwargs):
        if symbol not in fixtures:
            raise ProviderNotWiredError(symbol, "unknown")
        return None, symbol, fixtures[symbol]

    return _resolve


def test_perfectly_correlated_symbols_score_close_to_one(monkeypatch):
    base = [100.0 + i + (i % 5) * 0.7 for i in range(60)]  # trend + noise, never flat
    same = [p * 2.0 for p in base]  # scaled copy -- identical log returns
    monkeypatch.setattr(
        correlation_engine, "resolve_and_fetch", _fake_resolve_and_fetch({"AAA": _candles(base), "BBB": _candles(same)})
    )

    result = compute_correlation_matrix(["AAA", "BBB"], timeframe="1h", limit=60)

    assert result.symbols == ["AAA", "BBB"]
    assert result.matrix[0][0] == 1.0
    assert result.matrix[1][1] == 1.0
    assert result.matrix[0][1] == pytest.approx(1.0, abs=1e-9)
    assert result.matrix[0][1] == result.matrix[1][0]
    assert not result.skipped


def test_inversely_correlated_symbols_score_close_to_minus_one(monkeypatch):
    base = [100.0 + i + (i % 5) * 0.7 for i in range(60)]
    inverse = [200.0 - p for p in base]  # not literally 1/base, but a monotonic inverse response
    # Build a true inverse in *returns* space instead: mirror the return sequence.
    returns = [base[i + 1] / base[i] for i in range(len(base) - 1)]
    inverse_prices = [100.0]
    for r in returns:
        inverse_prices.append(inverse_prices[-1] / r)
    monkeypatch.setattr(
        correlation_engine,
        "resolve_and_fetch",
        _fake_resolve_and_fetch({"AAA": _candles(base), "CCC": _candles(inverse_prices)}),
    )

    result = compute_correlation_matrix(["AAA", "CCC"], timeframe="1h", limit=60)

    assert result.matrix[0][1] == pytest.approx(-1.0, abs=1e-9)


def test_unresolvable_symbol_is_reported_as_skipped_not_a_crash(monkeypatch):
    base = [100.0 + i for i in range(60)]
    monkeypatch.setattr(
        correlation_engine, "resolve_and_fetch", _fake_resolve_and_fetch({"AAA": _candles(base), "BBB": _candles(base)})
    )

    result = compute_correlation_matrix(["AAA", "BBB", "GHOST"], timeframe="1h", limit=60)

    assert "GHOST" not in result.symbols
    assert any(s.symbol == "GHOST" and s.reason == "no_data_or_not_wired" for s in result.skipped)
    assert result.symbols == ["AAA", "BBB"]


def test_symbols_with_no_time_overlap_are_all_skipped(monkeypatch):
    base = [100.0 + i for i in range(60)]
    monkeypatch.setattr(
        correlation_engine,
        "resolve_and_fetch",
        _fake_resolve_and_fetch(
            {
                "AAA": _candles(base, start_time=0),
                "BBB": _candles(base, start_time=10_000_000_000),  # disjoint clock
            }
        ),
    )

    result = compute_correlation_matrix(["AAA", "BBB"], timeframe="1h", limit=60)

    assert result.symbols == []
    assert result.matrix == []
    assert {s.symbol for s in result.skipped} == {"AAA", "BBB"}
    assert all(s.reason == "insufficient_overlap" for s in result.skipped)


def test_single_resolvable_symbol_returns_a_1x1_identity_matrix(monkeypatch):
    base = [100.0 + i for i in range(60)]
    monkeypatch.setattr(
        correlation_engine, "resolve_and_fetch", _fake_resolve_and_fetch({"AAA": _candles(base)})
    )

    result = compute_correlation_matrix(["AAA", "GHOST"], timeframe="1h", limit=60)

    assert result.symbols == ["AAA"]
    assert result.matrix == [[1.0]]


def test_price_method_correlates_raw_closes_instead_of_returns(monkeypatch):
    base = [100.0 + i for i in range(60)]
    same = [p * 3.0 + 5.0 for p in base]  # linear transform -- perfectly correlated in price too
    monkeypatch.setattr(
        correlation_engine, "resolve_and_fetch", _fake_resolve_and_fetch({"AAA": _candles(base), "BBB": _candles(same)})
    )

    result = compute_correlation_matrix(["AAA", "BBB"], timeframe="1h", limit=60, method="price")

    assert result.method == "price"
    assert result.matrix[0][1] == pytest.approx(1.0, abs=1e-9)


def test_invalid_method_raises_value_error(monkeypatch):
    with pytest.raises(ValueError, match="invalid_method"):
        compute_correlation_matrix(["AAA", "BBB"], method="bogus")


def test_flat_series_yields_none_not_zero(monkeypatch):
    flat = [100.0] * 60
    trending = [100.0 + i for i in range(60)]
    monkeypatch.setattr(
        correlation_engine,
        "resolve_and_fetch",
        _fake_resolve_and_fetch({"FLAT": _candles(flat), "TREND": _candles(trending)}),
    )

    result = compute_correlation_matrix(["FLAT", "TREND"], timeframe="1h", limit=60, method="price")

    assert result.matrix[0][1] is None
    assert result.matrix[1][0] is None
    # Diagonal stays 1.0 even for a flat series -- "a == b" short-circuits
    # before the undefined-variance correlation would ever be attempted.
    assert result.matrix[0][0] == 1.0
