"""VP3 metrics / folds / bootstrap / DSR unit tests (no full VP1 runs)."""

from __future__ import annotations

import math

from vp3.bootstrap import bootstrap_mean_ci, paired_block_delta_ci
from vp3.dsr import deflated_sharpe_ratio, probabilistic_sharpe_ratio
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
    # mean = 0; one -1 and one +1 → downside_dev = sqrt(0.5) over ALL bars
    rets = [-1.0, 1.0]
    s = sortino_ratio(rets, n_year=1.0)
    assert s is not None
    assert abs(s - (0.0 / math.sqrt(0.5))) < 1e-12  # mean 0 → Sortino 0


def test_equity_metrics_sharpe_cagr():
    # Steady +1% per bar from 100 (no downside → Sortino undefined / None)
    t0 = 1_700_000_000
    curve = [(t0 + i * 3600, 100.0 * (1.01**i), 0.0) for i in range(11)]
    m = equity_metrics(curve, interval="1h", equity_start=100.0)
    assert m.n_bars == 11
    assert m.cagr is not None and m.cagr > 0
    assert m.sharpe is not None and m.sharpe > 0
    assert m.sortino is None  # no negative bars → downside_dev = 0
    assert m.max_drawdown == 0.0
    # With a drawdown bar, Sortino is defined
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
    ci = paired_block_delta_ci(r, r, interval="1h", n_boot=300, seed=7)
    assert not ci.excludes_zero
    assert abs(ci.mean) < 1e-12


def test_dsr_psr_smoke():
    psr = probabilistic_sharpe_ratio(1.5, n_obs=100)
    assert psr is not None and 0.0 < psr <= 1.0
    dsr = deflated_sharpe_ratio(1.5, n_obs=100, n_trials=5)
    assert dsr is not None and dsr <= psr
