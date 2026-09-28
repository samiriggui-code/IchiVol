"""OF-0 — contrôles exigés avant le run (RS-07 §9)."""

from __future__ import annotations

import io
import math
import random
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from rs.of0 import HOUR_MS
from rs.of0.data import iter_hours, iter_seconds
from rs.of0.features import HourBar, aggregate, atr_series, baseline, bucket_width, design_row, of_features
from rs.of0.stats import day_block_bootstrap_ic, ols, ranks, spearman

T0 = int(datetime(2024, 3, 1, tzinfo=timezone.utc).timestamp() * 1000)


def sec(i: int, price: float, vol: float = 1.0, tb: float = 0.5, hi: float | None = None, lo: float | None = None):
    h = price if hi is None else hi
    l = price if lo is None else lo
    return (T0 + i * 1000, price, h, l, price, vol, tb)


# --- données ---------------------------------------------------------------

def _zip(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "x.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("x.csv", text)
    return p


def test_iter_seconds_header_us_and_2025_guard(tmp_path):
    ok = _zip(tmp_path, "open_time,o,h,l,c,v,ct,q,n,tb,tq,i\n"
              "1709251200000,1,2,0.5,1.5,10,0,0,0,4,0,0\n"
              "1709251201000000,1,2,0.5,1.5,10,0,0,0,4,0,0\n")
    got = list(iter_seconds(ok))
    assert [g[0] for g in got] == [1709251200000, 1709251201000] and got[0][6] == 4.0
    bad = _zip(tmp_path, "1735689600000,1,2,0.5,1.5,10,0,0,0,4,0,0\n")
    with pytest.raises(AssertionError):
        list(iter_seconds(bad))


def test_iter_hours_groups_utc_hours():
    secs = [sec(i, 100) for i in (0, 1, 3599, 3600, 3601)]
    hours = list(iter_hours(iter(secs)))
    assert [h for h, _ in hours] == [T0, T0 + HOUR_MS]
    assert [len(s) for _, s in hours] == [3, 2]


def test_aggregate_sums_volume_and_taker_buy():
    b = aggregate(T0, [sec(0, 100, 2, 1.5, hi=101), sec(1, 99, 3, 0.5, lo=98)])
    assert (b.open, b.high, b.low, b.close, b.volume, b.taker_buy) == (100, 101, 98, 99, 5, 2.0)


# --- grille causale ----------------------------------------------------------

def test_atr_simple_mean_and_width_uses_previous_bar():
    bars = [HourBar(T0 + i * HOUR_MS, 100, 100 + i, 100 - i, 100, 1, 0.5, 3600) for i in range(16)]
    atr = atr_series(bars, period=14)
    assert atr[12] is None and atr[13] == pytest.approx(sum(2 * i for i in range(14)) / 14)
    # w[t] vient de ATR[t−1] : modifier la barre t ne change pas w[t].
    w_before = bucket_width(atr[14])
    bars2 = bars[:15] + [HourBar(bars[15].t, 100, 1e6, 1, 100, 1, 0.5, 3600)]
    assert bucket_width(atr_series(bars2, period=14)[14]) == w_before


# --- F1–F5 -------------------------------------------------------------------

def test_poc_loc_and_extremes():
    # Range 100..110, gros volume à 101 (bas), delta acheteur en haut, vendeur en bas.
    secs = [sec(0, 110, 1, 1.0)] + [sec(i, 101, 10, 2.0) for i in range(1, 10)] + [sec(10, 100, 1, 0.0)]
    f = of_features(secs, w=1.0)
    assert f["F1_poc_loc"] == pytest.approx((101.5 - 100) / 10)
    vol = 1 + 90 + 1
    assert f["F2_delta_top"] == pytest.approx(1.0 / vol)  # seule la seconde à 110 est dans [108, 110]
    assert f["F3_delta_bot"] == pytest.approx((9 * (4 - 10) + (0 - 1)) / vol)  # 101 et 100 dans [100, 102]


def test_poc_tie_takes_lowest_bucket():
    secs = [sec(0, 100, 5), sec(1, 105, 5), sec(2, 110, 1)]
    assert of_features(secs, w=1.0)["F1_poc_loc"] == pytest.approx(0.05)


def test_delta_path_position_of_final_delta():
    # Delta cumulé : +1, +2, +3, puis −1 ×4 → final −1, max 3, min −1 → position −1.
    secs = [sec(i, 100 + i, 1, 1.0) for i in range(3)] + [sec(3 + i, 103, 1, 0.0) for i in range(4)]
    assert of_features(secs, w=1.0)["F4_delta_path"] == pytest.approx(-1.0)


def test_degenerate_cases():
    flat = [sec(i, 100, 1, 0.5) for i in range(40)]
    f = of_features(flat, w=1.0)
    assert f["F1_poc_loc"] is None and f["F2_delta_top"] is None and f["F4_delta_path"] is None
    assert f["F5_burst_share"] == pytest.approx(36 / 40)
    assert of_features([sec(0, 100, 0, 0)], w=1.0)["F5_burst_share"] is None


def test_burst_share_top_36_seconds():
    secs = [sec(i, 100 + (i % 2), 10 if i < 36 else 1, 0.5) for i in range(100)]
    assert of_features(secs, w=1.0)["F5_burst_share"] == pytest.approx(360 / (360 + 64))


def test_c2_counts_volume_spanning_buckets():
    secs = [sec(0, 100.5, 3, 1, hi=100.9, lo=100.1), sec(1, 101, 2, 1, hi=101.5, lo=100.5)]
    assert of_features(secs, w=1.0)["c2_multi_bucket_vol"] == 2


def test_features_causal_truncation():
    rng = random.Random(1)
    secs = [sec(i, 100 + rng.random(), rng.random(), rng.random() * 0.5) for i in range(3600)]
    a = of_features(secs, w=0.05)
    later = secs + [sec(3600 + i, 500, 1e6, 1e6) for i in range(10)]
    # Les mesures de l'heure t ne dépendent que des secondes de t (regroupement par heure).
    (h0, first), = [x for x in iter_hours(iter(later)) if x[0] == T0]
    assert of_features(first, w=0.05) == a


# --- référence et statistiques -----------------------------------------------

def test_baseline_and_design_row():
    bar = HourBar(T0, 100, 110, 90, 105, 50, 30, 3600)
    base = baseline(bar, 10.0, [25.0] * 20)
    assert base == pytest.approx([0.5, math.log(1.05), 0.2, 2.0, 0.25, 0.5, math.log(2)])
    assert len(design_row(base)) == 16
    assert baseline(bar, None, [25.0] * 20) is None
    assert baseline(bar, 10.0, [25.0] * 19) is None


def test_ols_recovers_exact_linear_relation():
    rng = random.Random(3)
    x = [[rng.random(), rng.random()] for _ in range(200)]
    y = [2 * a - 3 * b + 1 for a, b in x]
    _, r2, e = ols(x, y)
    assert r2 == pytest.approx(1.0) and max(abs(v) for v in e) < 1e-9


def test_spearman_and_ranks():
    assert ranks([3, 1, 2, 2]) == [4.0, 1.0, 2.5, 2.5]
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)


def test_bootstrap_ic_contains_point_estimate():
    rng = random.Random(5)
    a = [rng.gauss(0, 1) for _ in range(2000)]
    b = [x * 0.3 + rng.gauss(0, 1) for x in a]
    lo, hi = day_block_bootstrap_ic(ranks(a), ranks(b), [i // 24 for i in range(2000)], n=500, seed=7, alpha=0.05)
    ic = spearman(a, b)
    assert lo < ic < hi and lo > 0
