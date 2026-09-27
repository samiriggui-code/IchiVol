"""Unit tests for VP-NT1 annualized DSR helpers (no live VP1 data)."""

from __future__ import annotations

import math

from vp3.dsr import expected_max_sr, probabilistic_sharpe_ratio
from vp3.nt1_run import (
    BPY,
    bars_per_year,
    dsr_ann_scaled,
    sigma_and_sr_star,
    sr_ann_from_bar,
    sr_bar_from_ann,
)


def test_same_sr_ann_same_dsr_1h_and_4h_equal_n_obs():
    """Same SR_ann ⇒ same DSR at equal n_obs across TF (scale-invariant via SR*)."""
    sr_ann = 1.2
    n_obs = 500
    skew, kurt = 0.1, 3.2
    # pick a common SR*_ann
    sr_star_ann = 0.4
    for interval in ("1h", "4h"):
        sr_b = sr_bar_from_ann(sr_ann, interval)
        dsr = dsr_ann_scaled(
            sr_b=sr_b,
            n_obs=n_obs,
            skew=skew,
            kurt=kurt,
            interval=interval,
            sr_star_ann=sr_star_ann,
        )
        # store / compare
        if interval == "1h":
            d1 = dsr
        else:
            d4 = dsr
    assert d1 is not None and d4 is not None
    assert abs(d1 - d4) < 1e-12


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
    # larger σ → larger SR*
    srs_wide = [x * 3 for x in srs]
    sigma_w, star_w = sigma_and_sr_star(srs_wide, n_trials=5)
    assert sigma_w > sigma
    assert star_w > star5


def test_bpy_constants():
    assert bars_per_year("1h") == 8760
    assert bars_per_year("4h") == 2190
    assert BPY["1h"] == 8760.0
    # round-trip
    sb = 0.01
    assert abs(sr_bar_from_ann(sr_ann_from_bar(sb, "1h"), "1h") - sb) < 1e-15


def test_expected_max_sr_n1_is_zero():
    assert expected_max_sr(1, 0.5) == 0.0
    assert expected_max_sr(10, 0.0) == 0.0
