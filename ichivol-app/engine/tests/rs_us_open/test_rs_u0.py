"""RS-U0 — contrôles exigés avant calcul (RS-05 §8)."""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime, timezone

import pytest

from rs.us_open import BAR_MS, HORIZON_BARS, RANGE_BARS, round_trip_cost_bps
from rs.us_open.data import assert_no_reserved, parse_zip, truncate
from rs.us_open.measure import measure
from rs.us_open.nyse import PARIS, anchor_ms, nyse_days

A = int(datetime(2024, 3, 5, 14, 30, tzinfo=timezone.utc).timestamp() * 1000)


def flat_bars(start_ms: int, n: int, price: float = 100.0, hi: float = 101.0, lo: float = 99.0) -> dict:
    return {start_ms + i * BAR_MS: (price, hi, lo, price, 10.0) for i in range(n)}


def series(sweep: list[tuple[float, float, float, float]], after_open: float = 100.0, exit_open: float = 99.0) -> dict:
    """Range 6 h plat [99, 101], puis barres de balayage, puis horizon."""
    bars = flat_bars(A - RANGE_BARS * BAR_MS, RANGE_BARS)
    for i, (o, h, l, c) in enumerate(sweep):
        bars[A + i * BAR_MS] = (o, h, l, c, 10.0)
    t = A + len(sweep) * BAR_MS
    for i in range(3 + HORIZON_BARS + 2):
        bars.setdefault(t + i * BAR_MS, (after_open, 100.5, 99.5, after_open, 10.0))
    return bars


# --- conversion horaire ---------------------------------------------------

def test_ny_0930_summer_and_winter_utc():
    assert anchor_ms(date(2024, 7, 1), 570) == int(datetime(2024, 7, 1, 13, 30, tzinfo=timezone.utc).timestamp() * 1000)
    assert anchor_ms(date(2024, 1, 8), 570) == int(datetime(2024, 1, 8, 14, 30, tzinfo=timezone.utc).timestamp() * 1000)


def test_us_eu_dst_mismatch_week():
    # 2024-03-11 : US déjà en heure d'été, Paris pas encore → 15:30 Paris ≠ 09:30 NY.
    d = date(2024, 3, 11)
    assert anchor_ms(d, 15 * 60 + 30, PARIS) != anchor_ms(d, 570)
    assert anchor_ms(d, 570) == int(datetime(2024, 3, 11, 13, 30, tzinfo=timezone.utc).timestamp() * 1000)
    # Semaine normale : identiques.
    d2 = date(2024, 4, 15)
    assert anchor_ms(d2, 15 * 60 + 30, PARIS) == anchor_ms(d2, 570)


def test_nyse_days_excludes_weekends_and_holidays():
    days = nyse_days(date(2024, 7, 1), date(2024, 7, 7))
    assert date(2024, 7, 4) not in days
    assert date(2024, 7, 6) not in days
    assert days == [date(2024, 7, 1), date(2024, 7, 2), date(2024, 7, 3), date(2024, 7, 5)]


# --- range, balayage, confirmation ----------------------------------------

def test_range_excludes_anchor_bar():
    # La barre A monte à 103 et clôture à 100.5 : balayage haut du range [99, 101],
    # pas un range élargi à 103.
    bars = series([(100.0, 103.0, 99.5, 100.5)])
    a = measure(bars, A)
    assert a.status == "event" and a.side == -1


def test_sweep_high_then_return_is_short_with_entry_exit_opens():
    bars = series([(100.0, 102.0, 99.5, 100.5)], after_open=100.0)
    c = A
    bars[c + BAR_MS] = (100.0, 100.2, 99.8, 100.0, 10.0)  # entrée open[c+1]
    bars[c + (HORIZON_BARS + 1) * BAR_MS] = (99.0, 99.1, 98.9, 99.0, 10.0)  # sortie open[c+13]
    a = measure(bars, A)
    assert a.status == "event" and a.side == -1 and a.confirm_ms == c
    assert a.r_bps == pytest.approx(-1 * (99.0 / 100.0 - 1) * 1e4)  # +100 bps pour le short


def test_sweep_low_confirmed_on_later_bar_is_long():
    bars = series([(100.0, 100.5, 98.0, 98.5), (98.5, 99.5, 98.2, 99.2)])
    a = measure(bars, A)
    assert a.status == "event" and a.side == 1 and a.confirm_ms == A + BAR_MS


def test_same_bar_both_sides_is_ambiguous():
    bars = series([(100.0, 102.0, 98.0, 100.0)])
    assert measure(bars, A).status == "ambiguous"


def test_other_side_swept_before_confirmation_is_ambiguous():
    bars = series([(100.0, 102.0, 100.0, 101.5), (101.5, 101.8, 98.5, 99.5)])
    assert measure(bars, A).status == "ambiguous"


def test_no_return_and_no_sweep():
    assert measure(series([(101, 102, 101, 101.5)] * 3), A).status == "sweep_no_return"
    assert measure(series([(100, 100.5, 99.5, 100)] * 3), A).status == "none"


def test_missing_bar_excludes():
    bars = series([(100.0, 102.0, 99.5, 100.5)])
    del bars[A - 10 * BAR_MS]
    assert measure(bars, A).status == "excluded"
    bars = series([(100.0, 102.0, 99.5, 100.5)])
    del bars[A + (HORIZON_BARS + 1) * BAR_MS]
    assert measure(bars, A).status == "excluded"


def test_mae_mfe_in_r_of_sweep_extreme():
    bars = series([(100.0, 102.0, 99.5, 100.5)])
    bars[A + BAR_MS] = (100.0, 100.5, 99.0, 100.0, 10.0)
    a = measure(bars, A)
    # risque = |100 − 102| = 2 ; plus haut tenu 100.5 → MAE 0.25 R ; plus bas 99.0 → MFE 0.5 R.
    assert a.mae_r == pytest.approx(0.25) and a.mfe_r == pytest.approx(0.5)


# --- causalité -------------------------------------------------------------

def test_signal_does_not_depend_on_bars_after_confirmation():
    bars = series([(100.0, 102.0, 99.5, 100.5)])
    full = measure(bars, A)
    cut = {t: b for t, b in bars.items() if t <= full.confirm_ms}
    # Tronquée à c : pas d'horizon → exclu, mais le balayage et la confirmation
    # ne changent pas si on remplace le futur par autre chose.
    changed = dict(bars)
    for t in list(changed):
        if t > full.confirm_ms + (HORIZON_BARS + 1) * BAR_MS:
            changed[t] = (500.0, 600.0, 1.0, 500.0, 1e9)
    other = measure(changed, A)
    assert (other.side, other.confirm_ms, other.r_bps) == (full.side, full.confirm_ms, full.r_bps)
    assert measure(cut, A).status == "excluded"


# --- données et coûts ------------------------------------------------------

def test_truncation_asserts_no_2025():
    t25 = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    bars = {t25 - BAR_MS: (1, 1, 1, 1, 1), t25: (1, 1, 1, 1, 1)}
    assert list(truncate(bars)) == [t25 - BAR_MS]
    with pytest.raises(AssertionError):
        assert_no_reserved(bars)


def test_parse_zip_skips_header_and_converts_us():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.csv", "open_time,open,high,low,close,volume\n1709251200000,1,2,0.5,1.5,10\n1735689600000000,1,2,0.5,1.5,10\n")
    bars = parse_zip(buf.getvalue())
    assert set(bars) == {1709251200000, 1735689600000}


def test_round_trip_costs():
    assert round_trip_cost_bps("BTCUSDT") == 17.0
    assert round_trip_cost_bps("ETHUSDT") == 17.0
    assert round_trip_cost_bps("SOLUSDT") == 18.0
