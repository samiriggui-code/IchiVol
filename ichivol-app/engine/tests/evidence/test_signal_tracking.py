from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.types import Direction
from app.db.models import SignalEvidenceRecord
from app.evidence.context import ConfluenceContext, SignalContext
from app.evidence.engine import EvidenceReport
from app.evidence.matching import MatchStats
from app.evidence.outcome_stats import MIN_N, OutcomeRow, summarize_outcomes
from app.evidence.outcomes import compute_outcome, select_bars_after, update_pending_outcomes
from app.evidence.recorder import record_signal_evidence
from app.evidence.sample import SampleQuality
from app.indicators.ichimoku import Candle
from app.market_data.volume_semantics import VolumeType

HOUR = 3600
T0 = int(datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc).timestamp())


def _bar(t: int, o: float, h: float, low: float, c: float) -> Candle:
    return Candle(
        time=t, open=o, high=h, low=low, close=c, volume=1.0, volume_type=VolumeType.EXCHANGE_VOLUME
    )


# ---- pure outcome maths -------------------------------------------------


def test_long_forward_returns_are_positive_when_price_rises():
    bars = [_bar(T0 + HOUR * (i + 1), 100, 103 + i, 99, 101 + i) for i in range(5)]
    out = compute_outcome("LONG", 100.0, bars)
    assert out["forward_returns"]["1"] == pytest.approx(0.01)
    assert out["forward_returns"]["5"] == pytest.approx(0.05)
    assert "10" not in out["forward_returns"]
    assert out["bars_observed"] == 5 and out["complete"] is False


def test_short_signs_are_inverted_so_positive_still_means_right():
    bars = [_bar(T0 + HOUR, 100, 101, 95, 96)]
    out = compute_outcome("SHORT", 100.0, bars)
    assert out["forward_returns"]["1"] == pytest.approx(0.04)
    assert out["mfe_pct"] == pytest.approx(0.05)  # lowest low 95: 5 % in our favour
    assert out["mae_pct"] == pytest.approx(-0.01)  # highest high 101: 1 % against


def test_mfe_mae_and_completion_after_the_longest_horizon():
    bars = [_bar(T0 + HOUR * (i + 1), 100, 102, 98, 100) for i in range(20)]
    out = compute_outcome("LONG", 100.0, bars)
    assert out["complete"] is True
    assert out["mfe_pct"] == pytest.approx(0.02) and out["mae_pct"] == pytest.approx(-0.02)
    assert set(out["forward_returns"]) == {"1", "3", "5", "10", "20"}


def test_bars_still_forming_and_the_signal_bar_itself_are_never_used():
    candles = [_bar(T0, 1, 1, 1, 1), _bar(T0 + HOUR, 1, 1, 1, 1), _bar(T0 + 2 * HOUR, 1, 1, 1, 1)]
    now = T0 + 2 * HOUR + 600  # the last bar opened 10 minutes ago: not closed
    after = select_bars_after(candles, T0, HOUR, now)
    assert [c.time for c in after] == [T0 + HOUR]


# ---- confluence statistics ---------------------------------------------


def _row(stages=None, decision="WATCH", ret=0.01, first=True):
    return OutcomeRow(
        "LONG", decision, stages or {}, "crypto", {"5": ret, "10": ret, "20": ret}, first_of_run=first
    )


def test_groups_are_nested_and_flag_small_samples():
    rows = [
        _row({"participation": "pass", "structure": "pass"}, "BUY"),
        _row({"participation": "pass", "structure": "fail"}),
        _row({}),
    ]
    groups = {g["id"]: g for g in summarize_outcomes(rows)["groups"]}
    counts = [groups[k]["n_signals"] for k in ("ichimoku", "rvol", "rvol_structure", "pipeline")]
    assert counts == [3, 2, 1, 1]
    assert groups["ichimoku"]["horizons"]["5"]["small_sample"] is True
    assert MIN_N == 30


def test_only_the_first_bar_of_a_run_counts_by_default():
    rows = [_row(first=True), _row(first=False), _row(first=False)]
    assert summarize_outcomes(rows)["n_used"] == 1
    assert summarize_outcomes(rows, first_of_run_only=False)["n_used"] == 3


def test_hit_rate_and_mean_return():
    rows = [_row(ret=0.02), _row(ret=-0.01), _row(ret=0.01), _row(ret=-0.02)]
    h = summarize_outcomes(rows)["groups"][0]["horizons"]["5"]
    assert h["hit_rate"] == pytest.approx(0.5)
    assert h["mean_return"] == pytest.approx(0.0)


# ---- recorder + outcome pass on a real (in-memory) database -------------


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    SignalEvidenceRecord.__table__.create(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


def _report(ts: int, decision: str = "BUY") -> EvidenceReport:
    ctx = SignalContext(
        symbol="BTCUSDT",
        timeframe="1h",
        timestamp=ts,
        asset_class="crypto",
        provider="binance",
        confluence=ConfluenceContext(
            pipeline_decision=decision,
            direction="LONG",
            stage_statuses={"direction": "pass", "participation": "pass", "structure": "pass"},
        ),
    )
    hist = MatchStats(
        sample_size=0,
        sample_quality=SampleQuality.NO_DATA,
        status="NO_DATA",
        mean_return_pct=None,
        median_return_pct=None,
        favorable_rate=None,
        mean_mfe_pct=None,
        mean_mae_pct=None,
        horizon=5,
    )
    return EvidenceReport(
        context=ctx,
        evidence_engine_version="t",
        rules_version="t",
        feature_version="t",
        strategy_version="t",
        historical=hist,
    )


def _scan_row(ts: int, decision="BUY", direction=Direction.LONG, price=100.0):
    return SimpleNamespace(
        symbol="BTCUSDT",
        timeframe="1h",
        price=price,
        candles=[_bar(ts, 1, 1, 1, 1)],
        pipeline=SimpleNamespace(decision=decision, direction=direction),
        evidence=_report(ts, decision),
    )


def test_a_directional_signal_is_recorded_once_per_bar_and_refreshed_while_it_forms(session):
    assert record_signal_evidence(session, _scan_row(T0)) == "created"
    assert record_signal_evidence(session, _scan_row(T0)) is None  # nothing changed
    assert record_signal_evidence(session, _scan_row(T0, decision="WATCH")) == "updated"
    assert session.query(SignalEvidenceRecord).count() == 1
    assert session.query(SignalEvidenceRecord).one().decision == "WATCH"


def test_neutral_direction_records_nothing(session):
    assert record_signal_evidence(session, _scan_row(T0, direction=Direction.NEUTRAL)) is None
    assert session.query(SignalEvidenceRecord).count() == 0


def test_consecutive_bars_in_the_same_direction_are_one_run(session):
    record_signal_evidence(session, _scan_row(T0))
    record_signal_evidence(session, _scan_row(T0 + HOUR))
    record_signal_evidence(session, _scan_row(T0 + 10 * HOUR))
    rows = session.query(SignalEvidenceRecord).order_by(SignalEvidenceRecord.timestamp)
    assert [r.market_snapshot["first_of_run"] for r in rows] == [True, False, True]


def test_outcome_is_measured_incrementally_then_frozen(session):
    record_signal_evidence(session, _scan_row(T0, price=100.0))
    session.commit()
    # Live row.price must NOT be stored as entry (AG0); entry set from first closed open.
    assert "price" not in (session.query(SignalEvidenceRecord).one().market_snapshot or {})
    candles = [_bar(T0 + HOUR * i, 100, 102, 99, 100 + i) for i in range(4)]  # signal bar + 3 closed
    now = T0 + 4 * HOUR + 60

    assert update_pending_outcomes(session, lambda s, tf: candles, now_ts=now) == 1
    rec = session.query(SignalEvidenceRecord).one()
    assert rec.market_snapshot["price"] == 100.0
    assert rec.market_snapshot["entry_source"] == "first_closed_open"
    assert rec.outcome_json["bars_observed"] == 3 and rec.outcome_recorded_at is None
    assert rec.outcome_json["forward_returns"]["3"] == pytest.approx(0.03)
    assert rec.outcome_json["entry_price"] == 100.0

    assert update_pending_outcomes(session, lambda s, tf: candles, now_ts=now) == 0  # nothing new

    more = candles + [_bar(T0 + HOUR * (4 + i), 100, 103, 99, 104) for i in range(18)]
    assert update_pending_outcomes(session, lambda s, tf: more, now_ts=T0 + 30 * HOUR) == 1
    rec = session.query(SignalEvidenceRecord).one()
    assert rec.outcome_json["complete"] is True and rec.outcome_recorded_at is not None
    assert record_signal_evidence(session, _scan_row(T0, decision="SELL")) is None  # frozen once measured


def test_entry_is_open_of_first_closed_bar_not_live_price_and_never_refreshed(session):
    """AG0: entry = open of first closed bar after signal; no live-price refresh."""
    record_signal_evidence(session, _scan_row(T0, price=999.0))
    session.commit()
    rec = session.query(SignalEvidenceRecord).one()
    assert "price" not in (rec.market_snapshot or {})

    # Refresh while forming must still not write live price.
    assert record_signal_evidence(session, _scan_row(T0, price=888.0, decision="WATCH")) == "updated"
    assert "price" not in (session.query(SignalEvidenceRecord).one().market_snapshot or {})

    candles = [
        _bar(T0, 100, 101, 99, 100),
        _bar(T0 + HOUR, 111.0, 120, 110, 115),  # first closed after → entry
        _bar(T0 + 2 * HOUR, 115, 118, 114, 116),
    ]
    now = T0 + 3 * HOUR + 60
    assert update_pending_outcomes(session, lambda s, tf: candles, now_ts=now) == 1
    rec = session.query(SignalEvidenceRecord).one()
    assert rec.market_snapshot["price"] == 111.0
    assert rec.outcome_json["entry_price"] == 111.0
    # h=1 return vs 111 open, not vs live 999
    assert rec.outcome_json["forward_returns"]["1"] == pytest.approx(115 / 111.0 - 1.0)

    # Second pass: entry frozen even if more bars arrive
    more = candles + [_bar(T0 + 3 * HOUR, 200, 201, 199, 200)]
    update_pending_outcomes(session, lambda s, tf: more, now_ts=T0 + 4 * HOUR + 60)
    assert session.query(SignalEvidenceRecord).one().market_snapshot["price"] == 111.0


def test_a_signal_that_left_the_provider_window_is_closed_as_stale(session):
    record_signal_evidence(session, _scan_row(T0))
    session.commit()
    recent = [_bar(T0 + 500 * HOUR + HOUR * i, 1, 1, 1, 1) for i in range(30)]
    assert update_pending_outcomes(session, lambda s, tf: recent, now_ts=T0 + 600 * HOUR) == 1
    rec = session.query(SignalEvidenceRecord).one()
    assert rec.outcome_json["stale"] is True and rec.outcome_recorded_at is not None
