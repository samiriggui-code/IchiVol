"""VP3 metrics / folds / bootstrap / DSR unit tests (no full VP1 runs)."""

from __future__ import annotations

import math

import pytest

from vp3.bootstrap import (
    BLOCK_MEAN,
    mean_block_length_sample,
    paired_block_delta_ci,
    bootstrap_mean_ci,
    stationary_block_indices,
)
from vp3.dsr import (
    deflated_sharpe_ratio,
    empirical_sr_std,
    expected_max_sr,
    probabilistic_sharpe_ratio,
    sample_skew_kurtosis,
)
from vp3.folds import WF_FOLDS, entry_gate_s, fold_test_window_s, purge_seconds
from vp3.metrics import bar_returns_from_equity, equity_metrics, sortino_ratio


def test_seven_wf_folds_and_purge():
    assert len(WF_FOLDS) == 7
    assert WF_FOLDS[0].id == "WF1"
    assert purge_seconds("1h") == 48 * 3600
    assert purge_seconds("4h") == 24 * 14400
    w0, w1 = fold_test_window_s(WF_FOLDS[0])
    gate = entry_gate_s(WF_FOLDS[0], "1h")
    assert gate == w0 + purge_seconds("1h")
    assert w1 > gate


def test_sortino_counts_all_bars_not_only_negatives():
    rets = [-1.0, 1.0]
    s = sortino_ratio(rets, n_year=1.0)
    assert s is not None
    assert abs(s - (0.0 / math.sqrt(0.5))) < 1e-12


def test_equity_metrics_sharpe_cagr():
    t0 = 1_700_000_000
    curve = [(t0 + i * 3600, 100.0 * (1.01**i), 0.0) for i in range(11)]
    m = equity_metrics(curve, interval="1h", equity_start=100.0)
    assert m.n_bars == 11
    assert m.cagr is not None and m.cagr > 0
    assert m.sharpe is not None and m.sharpe > 0
    assert m.sortino is None
    curve2 = curve + [(t0 + 11 * 3600, curve[-1][1] * 0.9, 0.0)]
    m2 = equity_metrics(curve2, interval="1h", equity_start=100.0)
    assert m2.sortino is not None


def test_bar_returns_length():
    curve = [(0, 100.0, 0.0), (1, 110.0, 0.0), (2, 99.0, 0.0)]
    r = bar_returns_from_equity(curve)
    assert len(r) == 2
    assert abs(r[0] - 0.1) < 1e-12


def test_bootstrap_trade_ci_excludes_zero_when_strong():
    vals = [1.0] * 50
    ci = bootstrap_mean_ci(vals, n_boot=500, seed=7)
    assert ci.excludes_zero and ci.lo > 0


def test_paired_block_delta_identical_series_includes_zero():
    r = [0.01, -0.005, 0.002, 0.0] * 30
    times = list(range(len(r)))
    ci = paired_block_delta_ci(
        r, r, interval="1h", n_boot=300, seed=7, times_a=times, times_b=times
    )
    assert not ci.excludes_zero
    assert abs(ci.mean) < 1e-12


def test_paired_block_timestamp_mismatch_raises():
    r = [0.01] * 10
    with pytest.raises(ValueError, match="timestamp"):
        paired_block_delta_ci(
            r, r, interval="1h", n_boot=10, times_a=list(range(10)), times_b=list(range(1, 11))
        )


def test_stationary_block_mean_length_near_target():
    mean_len = mean_block_length_sample(10_000, BLOCK_MEAN["1h"], n_draws=8000, seed=7)
    assert 20.0 < mean_len < 28.0  # E[L]=24 for geometric p=1/24
    mean_4h = mean_block_length_sample(10_000, BLOCK_MEAN["4h"], n_draws=8000, seed=3)
    assert 4.5 < mean_4h < 7.5


def test_stationary_indices_cover_n():
    import random

    idx = stationary_block_indices(100, 24, random.Random(7))
    assert len(idx) == 100
    assert all(0 <= i < 100 for i in idx)


def test_dsr_n1_equals_psr():
    rets = [0.001, -0.0005, 0.0008, 0.0002] * 40
    mu = sum(rets) / len(rets)
    var = sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)
    sr = mu / math.sqrt(var)
    skew, kurt = sample_skew_kurtosis(rets)
    psr = probabilistic_sharpe_ratio(sr, len(rets), skew=skew, kurt=kurt, sr_benchmark=0.0)
    dsr = deflated_sharpe_ratio(sr, len(rets), n_trials=1, returns=rets)
    assert psr is not None and dsr is not None
    assert abs(dsr - psr) < 1e-12


def test_dsr_decreases_with_n_trials_not_crushed():
    # Synthetic edge: positive mean, small noise — SR ~ O(1e-1) per bar scale
    rets = [0.002 + ((i % 7) - 3) * 1e-4 for i in range(200)]
    mu = sum(rets) / len(rets)
    var = sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)
    sr = mu / math.sqrt(var)
    # Fake T10b trial SRs around same scale (not σ=1)
    base = [sr + (i - 5) * 0.01 for i in range(11)]
    d1 = deflated_sharpe_ratio(sr, len(rets), n_trials=1, returns=rets)
    d5 = deflated_sharpe_ratio(sr, len(rets), n_trials=5, returns=rets, trial_srs=base[:5])
    d11 = deflated_sharpe_ratio(sr, len(rets), n_trials=11, returns=rets, trial_srs=base)
    assert d1 is not None and d5 is not None and d11 is not None
    assert d1 >= d5 >= d11
    assert d11 > 0.05  # not crushed to ~0 by wrong σ=1 scale
    assert empirical_sr_std(base) < 0.5
    assert expected_max_sr(11, empirical_sr_std(base)) < expected_max_sr(11, 1.0)
