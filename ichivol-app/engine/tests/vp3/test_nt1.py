"""Unit tests for VP-NT1 DSR helpers + §9 verdict branches (no live VP1 data)."""

from __future__ import annotations

from vp3.bootstrap import BootstrapCI
from vp3.dsr import expected_max_sr, probabilistic_sharpe_ratio
from vp3.nt1_run import (
    BPY,
    apply_adverse_final,
    bars_per_year,
    dsr_bar_scaled,
    fold_sign_instability,
    sigma_and_sr_star,
    sr_ann_from_bar,
    sr_bar_from_ann,
    verdict_compare,
)


def test_same_sr_ann_same_dsr_equal_duration():
    """Same SR_ann, n_obs_1h = 4 × n_obs_4h (equal duration), skew=0, kurt=3."""
    sr_ann = 1.2
    sr_star_ann = 0.4
    n4 = 2000
    n1 = 4 * n4
    d1 = dsr_bar_scaled(
        sr_b=sr_bar_from_ann(sr_ann, "1h"),
        n_obs=n1,
        skew=0.0,
        kurt=3.0,
        interval="1h",
        sr_star_ann=sr_star_ann,
    )
    d4 = dsr_bar_scaled(
        sr_b=sr_bar_from_ann(sr_ann, "4h"),
        n_obs=n4,
        skew=0.0,
        kurt=3.0,
        interval="4h",
        sr_star_ann=sr_star_ann,
    )
    assert d1 is not None and d4 is not None
    assert abs(d1 - d4) < 1e-3


def test_dsr_not_inflated():
    """Bar-scale PSR must not collapse to ~1.0 for mild edge + fat tails."""
    sr_ann = 0.5
    sr_star_ann = 0.3
    dsr = dsr_bar_scaled(
        sr_b=sr_bar_from_ann(sr_ann, "1h"),
        n_obs=52_000,
        skew=0.0,
        kurt=20.0,
        interval="1h",
        sr_star_ann=sr_star_ann,
    )
    assert dsr is not None
    assert 0.6 < dsr < 0.8


def test_n1_dsr_equals_psr_sr_star_zero():
    """N=1 → E[max]=0 → DSR = PSR(sr*=0)."""
    returns_sr_bar = 0.05
    n_obs = 200
    skew, kurt = 0.0, 3.0
    sigma, sr_star = sigma_and_sr_star([returns_sr_bar], n_trials=1)
    assert sigma == 0.0
    assert sr_star == 0.0
    dsr = probabilistic_sharpe_ratio(
        returns_sr_bar, n_obs, skew=skew, kurt=kurt, sr_benchmark=sr_star
    )
    psr0 = probabilistic_sharpe_ratio(
        returns_sr_bar, n_obs, skew=skew, kurt=kurt, sr_benchmark=0.0
    )
    assert dsr == psr0


def test_sr_star_ann_increases_with_n_and_sigma():
    srs = [0.1, 0.2, 0.0, -0.05, 0.15]
    sigma, star5 = sigma_and_sr_star(srs, n_trials=5)
    _, star20 = sigma_and_sr_star(srs, n_trials=20)
    assert star20 > star5 > 0
    srs_wide = [x * 3 for x in srs]
    sigma_w, star_w = sigma_and_sr_star(srs_wide, n_trials=5)
    assert sigma_w > sigma
    assert star_w > star5


def test_bpy_constants():
    assert bars_per_year("1h") == 8760
    assert bars_per_year("4h") == 2190
    assert BPY["1h"] == 8760.0
    sb = 0.01
    assert abs(sr_bar_from_ann(sr_ann_from_bar(sb, "1h"), "1h") - sb) < 1e-15


def test_expected_max_sr_n1_is_zero():
    assert expected_max_sr(1, 0.5) == 0.0
    assert expected_max_sr(10, 0.0) == 0.0


def _edge_kwargs(**overrides):
    base = dict(
        bi="B2",
        bi_beats_bj=True,
        dsr_i=0.96,
        n_trades_i=50,
        expectancy_i=10.0,
        expectancy_ci_excludes_zero=True,
        n_positive_folds=5,
        fold_max_dds=[-0.1] * 7,
        fold_expectancies=[1.0] * 7,
    )
    base.update(overrides)
    return base


def test_verdict_edge_all_criteria():
    assert verdict_compare(**_edge_kwargs()) == "EDGE"


def test_verdict_edge_requires_trade_ic_excludes_zero():
    """(a) EDGE exige IC bootstrap trades exclut 0."""
    assert (
        verdict_compare(**_edge_kwargs(expectancy_ci_excludes_zero=False))
        == "PAS D'EDGE"
    )


def test_verdict_n_lt_40_non_concluant():
    """(c) N<40 → NON CONCLUANT."""
    assert verdict_compare(**_edge_kwargs(bi_beats_bj=False, n_trades_i=20)) == "NON CONCLUANT"


def test_verdict_n_ge_40_pas_d_edge():
    """(c) N≥40 and not EDGE → PAS D'EDGE."""
    assert (
        verdict_compare(**_edge_kwargs(bi_beats_bj=False, dsr_i=0.5, n_trades_i=50))
        == "PAS D'EDGE"
    )


def test_verdict_instability_priority():
    """(d) >3 folds opposite sign → NON CONCLUANT (priority over PAS D'EDGE)."""
    # agg +10, 4 folds negative → unstable; N≥40 would otherwise be PAS D'EDGE
    fold_exps = [-1.0, -1.0, -1.0, -1.0, 2.0, 2.0, 2.0]
    assert fold_sign_instability(fold_exps, 10.0) is True
    assert (
        verdict_compare(
            **_edge_kwargs(
                bi_beats_bj=False,
                dsr_i=0.5,
                n_trades_i=50,
                expectancy_i=10.0,
                fold_expectancies=fold_exps,
            )
        )
        == "NON CONCLUANT"
    )


def test_verdict_mdd_blocks_edge():
    """(b) maxDD ≥ 35% on any fold blocks EDGE (B1–B8)."""
    bad = [-0.1] * 6 + [-0.40]
    assert verdict_compare(**_edge_kwargs(fold_max_dds=bad)) == "PAS D'EDGE"


def test_verdict_final_base_edge_adverse_not():
    """(e) EDGE base but not adverse → verdict_final NON CONCLUANT."""
    base = [
        {
            "question": "A",
            "symbol": "BTCUSDT",
            "interval": "1h",
            "verdict": "EDGE",
            "verdict_final": "EDGE",
        }
    ]
    adv = [
        {
            "question": "A",
            "symbol": "BTCUSDT",
            "interval": "1h",
            "verdict": "PAS D'EDGE",
            "verdict_final": "PAS D'EDGE",
        }
    ]
    apply_adverse_final(base, adv)
    assert base[0]["verdict_final"] == "NON CONCLUANT"
    assert adv[0]["verdict_final"] == "NON CONCLUANT"


def test_verdict_final_both_edge_unchanged():
    base = [{"question": "B", "symbol": "ETHUSDT", "interval": "4h", "verdict": "EDGE", "verdict_final": "EDGE"}]
    adv = [{"question": "B", "symbol": "ETHUSDT", "interval": "4h", "verdict": "EDGE", "verdict_final": "EDGE"}]
    apply_adverse_final(base, adv)
    assert base[0]["verdict_final"] == "EDGE"
    assert adv[0]["verdict_final"] == "EDGE"
