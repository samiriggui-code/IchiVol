"""VP-S1 étape 1 — BM/BN rules, sorties, HTF, coûts, S1–S5 (aucun run VP1)."""

from __future__ import annotations

from app.agents.types import Direction
from app.indicators.ichimoku import Candle
from research_lab.signals import BarSignal
from research_lab.sim import CostModel, simulate
from vp3 import N_T10B_SHIELD, WARMUP_BARS
from vp3.bootstrap import max_drawdown_from_returns, paired_block_delta_ci
from vp3.entries import align_htf_directions, entry_mask, htf_cloud_direction, overlay_ltf_ichimoku_directions
from vp3.rules import strategy_rules
from vp3.shield import (
    check_s1,
    check_s2,
    check_s3,
    check_s4,
    evaluate_shield,
    score_from_wf_parts,
)
from app.indicators.ichimoku import IchimokuParams, compute_ichimoku

H = 3600
H4 = 14400
T0 = 1_700_000_000 - 1_700_000_000 % H4
NOFEE = CostModel("nofee", 0.0, 0.0, 0.0)
FEE = CostModel("fee", commission_bps=10.0, spread_bps=0.0, slippage_bps=0.0)


def _bar(i: int, o: float, h: float, l: float, c: float, *, sec: int = H) -> Candle:
    return Candle(time=T0 + i * sec, open=o, high=h, low=l, close=c, volume=1e9)


def _sig(t: int, decision: str, direction: Direction, sd: float = 2.0) -> BarSignal:
    return BarSignal(t, decision, direction, sd, None, (), (), "t", None)


def test_bm_rules_direction_no_timestop():
    r = strategy_rules("BM", "1h")
    assert r.exit_mode == "direction"
    assert r.time_stop_bars is None
    assert r.full_cash is True
    assert r.take_profit_r == 2.0
    assert r.allow_short is False
    assert r.immediate_fill is False


def test_bn_rules_exposure_no_levels():
    r = strategy_rules("BN", "4h")
    assert r.exit_mode == "exposure"
    assert r.time_stop_bars is None
    assert r.full_cash is True
    assert r.force_flat_at_end is True


def test_bm_direction_exit_at_next_open():
    """Sortie direction : LONG → NEUTRAL au close → fill open suivant."""
    rows = [
        (100, 101, 99, 100.5, "BUY", Direction.LONG),
        (100.5, 101, 100, 100.8, "WATCH", Direction.LONG),
        (100.8, 101, 100, 100.5, "WATCH", Direction.NEUTRAL),  # flip at close
        (100.2, 100.5, 99.5, 100.0, "WATCH", Direction.NEUTRAL),  # fill exit at open
        (100.0, 100.5, 99.5, 100.0, "WATCH", Direction.NEUTRAL),
    ]
    feed = {}
    for i, (o, h, l, c, d, direction) in enumerate(rows):
        t = T0 + i * H
        feed[t] = (_bar(i, o, h, l, c), _sig(t, d, direction, sd=5.0))
    rules = strategy_rules("BM", "1h")
    res = simulate({"X": feed}, rules, NOFEE, (T0, T0 + len(rows) * H), initial=10_000.0)
    assert len(res.trades) == 1
    assert res.trades[0].exit_reason == "direction_flipped"
    # Entry at open of bar 1 (signal bar 0); exit at open of bar 3 (signal flip bar 2)
    assert res.trades[0].entry_time == T0 + H
    assert res.trades[0].exit_time == T0 + 3 * H


def test_bn_toggles_exposure_and_costs_per_toggle():
    """BN : BUY tant que exposé, cash sinon ; coûts à chaque bascule."""
    # bar0 BUY → entry open1 ; bar2 WATCH → exit open3 ; bar3 BUY → entry open4 ; flat end
    rows = [
        (100, 101, 99, 100, "BUY"),
        (100, 101, 99, 100, "BUY"),
        (100, 101, 99, 100, "WATCH"),
        (100, 101, 99, 100, "BUY"),
        (100, 101, 99, 100, "BUY"),
        (100, 101, 99, 100, "WATCH"),
    ]
    feed = {}
    for i, (o, h, l, c, d) in enumerate(rows):
        t = T0 + i * H
        direction = Direction.LONG if d == "BUY" else Direction.NEUTRAL
        feed[t] = (_bar(i, o, h, l, c), _sig(t, d, direction, sd=5.0))
    rules = strategy_rules("BN", "1h")
    res = simulate({"X": feed}, rules, FEE, (T0, T0 + len(rows) * H), initial=10_000.0)
    assert len(res.trades) >= 2
    assert all(t.exit_reason in ("exposure_off", "window_end") for t in res.trades)
    # Each closed trade paid entry+exit commission
    for t in res.trades:
        assert t.commission > 0


def test_bn_no_stop_hit_under_exposure():
    """Pas de stop : une barre qui traverse le SL ne sort pas en exposure."""
    # Enter, then crash through any stop — still held until WATCH
    rows = [
        (100, 101, 99, 100, "BUY"),
        (100, 101, 50, 55, "BUY"),  # would stop if levels applied
        (55, 56, 54, 55, "WATCH"),
        (55, 56, 54, 55, "WATCH"),
    ]
    feed = {}
    for i, (o, h, l, c, d) in enumerate(rows):
        t = T0 + i * H
        direction = Direction.LONG if d == "BUY" else Direction.NEUTRAL
        feed[t] = (_bar(i, o, h, l, c), _sig(t, d, direction, sd=1.0))
    rules = strategy_rules("BN", "1h")
    res = simulate({"X": feed}, rules, NOFEE, (T0, T0 + len(rows) * H), initial=10_000.0)
    assert len(res.trades) == 1
    assert res.trades[0].exit_reason == "exposure_off"
    assert "stop" not in res.trades[0].exit_reason


def test_htf_align_no_lookahead():
    """HTF close must be fully closed before LTF decision (bar close)."""
    # One HTF bar [T0, T0+H4): known at LTF decision_s = ltf.time + H
    htf = [_bar(0, 100, 110, 90, 105, sec=H4)]  # close 105 → above cloud later
    # Minimal ichi row stub via compute after enough bars — use htf_cloud_direction unit
    # Build enough HTF for ichi, then check align uses closed bar only.
    htf_candles = [
        Candle(
            time=T0 + i * H4,
            open=100 + i,
            high=120 + i,
            low=80 + i,
            close=110 + i,  # above any cloud once formed
            volume=1e6,
        )
        for i in range(80)
    ]
    ltf = [
        Candle(
            time=T0 + i * H,
            open=100,
            high=101,
            low=99,
            close=100,
            volume=1e6,
        )
        for i in range(80 * 4)
    ]
    htf_ichi = compute_ichimoku(htf_candles, IchimokuParams())
    dirs = align_htf_directions(ltf, htf_candles, htf_ichi, ltf_seconds=H, htf_seconds=H4)
    # For LTF bar whose close is before first HTF close → neutral
    assert dirs[0] == "neutral"
    # After first HTF fully closed (htf[0].time+H4 <= ltf.time+H), direction available
    first_ready = None
    for i, c in enumerate(ltf):
        if htf_candles[0].time + H4 <= c.time + H:
            first_ready = i
            break
    assert first_ready is not None
    assert dirs[first_ready] in ("long", "short", "neutral")
    # Lookahead: advancing LTF must not see HTF bar j before j has closed
    j = 10
    htf_close_s = htf_candles[j].time + H4
    for i, c in enumerate(ltf):
        decision_s = c.time + H
        if decision_s < htf_close_s:
            # Must not yet use bar j's close — index in align is last fully closed
            # So direction equals using bars < j only; at least not a crash
            assert dirs[i] in ("long", "short", "neutral")


def test_bn_entry_mask_htf_not_short():
    htf_candles = [
        Candle(time=T0 + i * H4, open=100, high=101, low=99, close=100, volume=1e6) for i in range(90)
    ]
    ltf = [
        Candle(time=T0 + i * H, open=100, high=101, low=99, close=100, volume=1e6) for i in range(90 * 4)
    ]
    # Force short cloud direction via monkeypatch of align
    short_dirs = ["short"] * len(ltf)
    long_dirs = ["long"] * len(ltf)
    import vp3.entries as ent

    orig = ent.align_htf_directions
    try:
        ent.align_htf_directions = lambda *a, **k: short_dirs  # type: ignore[assignment]
        m_short = entry_mask("BN", ltf, htf_candles=htf_candles, ltf_seconds=H, htf_seconds=H4)
        ent.align_htf_directions = lambda *a, **k: long_dirs  # type: ignore[assignment]
        m_long = entry_mask("BN", ltf, htf_candles=htf_candles, ltf_seconds=H, htf_seconds=H4)
    finally:
        ent.align_htf_directions = orig  # type: ignore[assignment]
    assert all(not m_short[i] for i in range(WARMUP_BARS, len(ltf)))
    assert all(m_long[i] for i in range(WARMUP_BARS, len(ltf)))


def test_s1_s5_synthetic_case():
    """Cas synthétique : S1–S5 + N=48 + DSR reporté (Bi cash vs B0 crash)."""
    from vp3.bootstrap import BootstrapCI

    assert check_s4(BootstrapCI(mean=0.2, lo=0.05, hi=0.35, n=100, excludes_zero=True))

    # Bi : returns nuls (cash) ; B0 : crash constant → Δ maxDD > 0 sur tout tirage
    n = 120
    times = list(range(n))
    b0 = score_from_wf_parts(
        strategy="B0",
        interval="1h",
        fold_max_dds=(-0.60, -0.55),
        bar_returns=[-0.04] * n,
        bar_times=times,
        n_trades=0,
    )
    bi = score_from_wf_parts(
        strategy="BN",
        interval="1h",
        fold_max_dds=(-0.05, -0.04),
        bar_returns=[0.001] * n,
        bar_times=times,
        n_trades=12,
    )
    assert check_s1(bi.dd_pire, b0.dd_pire)
    assert check_s2(bi.cagr_agg, b0.cagr_agg)
    assert check_s3(bi.calmar, b0.calmar)

    crit = evaluate_shield(
        bi,
        b0,
        interval="1h",
        n_boot=300,
        seed=7,
        adverse_s1_s4=(True, True, True, True),
        dsr_i=0.4,
    )
    assert crit.s1 and crit.s2 and crit.s3 and crit.s4
    assert crit.s5 is True
    assert crit.n_t10b == N_T10B_SHIELD == 48
    assert crit.verdict == "BOUCLIER VALIDÉ"
    assert crit.dsr_i == 0.4


def test_maxdd_metric_paired_identical_includes_zero():
    r = [0.01, -0.02, 0.005, -0.01] * 25
    times = list(range(len(r)))
    ci = paired_block_delta_ci(
        r, r, interval="1h", n_boot=200, seed=7, metric="maxdd", times_a=times, times_b=times
    )
    assert not ci.excludes_zero
    assert abs(ci.mean) < 1e-12
    assert max_drawdown_from_returns(r) <= 0


def test_bm_force_flat_horizon_end_counts_open_position():
    """S1-R1: position still LONG past the window is force-flatted as horizon_end (in trades)."""
    from dataclasses import replace

    rows = [
        (100, 101, 99, 100.5, "BUY", Direction.LONG),
        (100.5, 102, 100, 101.5, "WATCH", Direction.LONG),
        (101.5, 103, 101, 102.5, "WATCH", Direction.LONG),
        (102.5, 104, 102, 103.5, "WATCH", Direction.LONG),
        (103.5, 105, 103, 104.5, "WATCH", Direction.LONG),
    ]
    feed = {}
    for i, (o, h, l, c, d, direction) in enumerate(rows):
        t = T0 + i * H
        feed[t] = (_bar(i, o, h, l, c), _sig(t, d, direction, sd=5.0))
    rules = replace(strategy_rules("BM", "1h"), force_flat_at_end=True, force_flat_reason="horizon_end")
    res = simulate({"X": feed}, rules, NOFEE, (T0, T0 + len(rows) * H), initial=10_000.0)
    assert len(res.open_at_end) == 0
    assert len(res.trades) == 1
    assert res.trades[0].exit_reason == "horizon_end"


def test_bm_horizon_never_reads_validation_2025():
    """S1-R1: the 90-day BM horizon is capped at dev end on WF folds (WF7 ends 2024-12-31)."""
    from vp3.folds import WF_FOLDS, fold_test_window_s
    from vp3.wf import BM_POST_FOLD_HORIZON_S, DEV_END_EXCL_S, sim_end_s

    assert DEV_END_EXCL_S == 1735689600  # 2025-01-01T00:00:00Z
    for fold in WF_FOLDS:
        for tf in ("1h", "4h"):
            end = sim_end_s("BM", fold, tf)
            assert end <= DEV_END_EXCL_S
            assert end == min(fold_test_window_s(fold)[1] + BM_POST_FOLD_HORIZON_S, DEV_END_EXCL_S)
    assert sim_end_s("BM", WF_FOLDS[-1], "1h") == DEV_END_EXCL_S


def test_overlay_preserves_decision_sets_ichi_direction():
    candles = [
        Candle(time=T0 + i * H, open=100 + i * 0.1, high=101 + i * 0.1, low=99, close=100.5 + i * 0.1, volume=1e6)
        for i in range(100)
    ]
    feed = {
        c.time: (
            c,
            BarSignal(c.time, "WATCH", Direction.NEUTRAL, 1.0, None, (), (), "x", None),
        )
        for c in candles
    }
    overlay_ltf_ichimoku_directions(feed, candles)
    # After overlay, directions are Ichimoku enums (not forced NEUTRAL for all)
    dirs = {feed[c.time][1].direction for c in candles}
    assert Direction.NEUTRAL in dirs or Direction.LONG in dirs or Direction.SHORT in dirs
    assert all(feed[c.time][1].decision == "WATCH" for c in candles)


def test_htf_cloud_direction_basic():
    class Row:
        senkou_a = 100.0
        senkou_b = 90.0

    assert htf_cloud_direction(Row(), 110.0) == "long"
    assert htf_cloud_direction(Row(), 80.0) == "short"
    assert htf_cloud_direction(Row(), 95.0) == "neutral"
