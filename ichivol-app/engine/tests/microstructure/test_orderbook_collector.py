"""OB-1 — carnet synchronisé, trous / doublons, agrégat 1 min, stockage, session de collecte (faux flux)."""

from __future__ import annotations

import gzip
import json

from app.microstructure.book.aggregate import MinuteAggregator
from app.microstructure.book.collector import CollectorConfig, SymbolSession
from app.microstructure.book.storage import iter_ndjson, latest_minute, purge_older_than, read_minutes, read_status
from app.microstructure.book.sync import BookState, DepthEvent, LocalBook
from app.microstructure.book.trades import AggTrade, TradeTracker

T0 = 1_790_000_040_000  # ms, 20 s after a minute boundary... (aligned below)
T0 = T0 - T0 % 60_000


def ev(U, u, bids=(), asks=(), E=None, rx=None):
    return DepthEvent(first_id=U, final_id=u, bids=tuple(bids), asks=tuple(asks), event_ms=E, received_ms=rx)


SNAP = {"lastUpdateId": 100, "bids": [["99", "1"], ["98", "2"], ["90", "5"]], "asks": [["101", "1"], ["102", "3"], ["110", "4"]]}


# --- sync ----------------------------------------------------------------------------------------


def test_buffer_then_snapshot_applies_only_bridging_events():
    b = LocalBook("BTCUSDT")
    assert b.state == BookState.UNAVAILABLE
    b.on_event(ev(90, 95, bids=[(99, 7)]))  # older than snapshot → dropped
    b.on_event(ev(96, 103, bids=[(99, 3)]))  # bridges lastUpdateId+1=101
    b.on_event(ev(104, 104, asks=[(101, 0)]))  # level removed
    r = b.apply_snapshot(SNAP)
    assert (r.applied, r.ignored_old, r.gap) == (2, 1, False)
    assert b.state == BookState.SYNCED and b.last_update_id == 104
    assert b.bids[99.0] == 3 and 101.0 not in b.asks
    assert b.best_bid() == (99.0, 3.0) and b.best_ask() == (102.0, 3.0)
    assert b.mid() == 100.5


def test_first_event_not_bridging_triggers_resync_and_keeps_buffer():
    b = LocalBook("BTCUSDT")
    b.on_event(ev(105, 110))  # snapshot (100) too old: 101..104 missing
    r = b.apply_snapshot(SNAP)
    assert r.need_snapshot and b.state == BookState.PARTIAL and b.last_update_id is None
    assert b.resyncs == 1 and len(b._buffer) == 1  # failing event kept for the next snapshot
    r2 = b.apply_snapshot({**SNAP, "lastUpdateId": 107})
    assert r2.applied == 1 and b.state == BookState.SYNCED and b.last_update_id == 110


def test_sequence_gap_marks_partial_and_requires_new_snapshot():
    b = LocalBook("BTCUSDT")
    b.on_event(ev(101, 101))
    b.apply_snapshot(SNAP)
    assert b.on_event(ev(102, 103)).applied == 1
    r = b.on_event(ev(105, 106))  # 104 missing
    assert r.gap and r.need_snapshot
    assert b.state == BookState.PARTIAL and not b.bids and b.gaps == 1  # nothing kept, nothing interpolated
    b.on_event(ev(107, 108))
    assert b.last_update_id is None and len(b._buffer) == 1  # buffering again until the next snapshot


def test_stale_after_silence_and_recovery():
    b = LocalBook("BTCUSDT")
    b.on_event(ev(101, 101, rx=T0))
    b.apply_snapshot(SNAP)
    assert b.refresh_state(T0 + 1500) == BookState.SYNCED
    assert b.refresh_state(T0 + 2500) == BookState.STALE
    b.on_alive(T0 + 2600)
    assert b.state == BookState.SYNCED


def test_coverage_marks_ranges_beyond_snapshot_depth():
    b = LocalBook("BTCUSDT")
    b.on_event(ev(101, 101))
    b.apply_snapshot(SNAP)
    assert b.covers(95, 105) and not b.covers(80, 105)
    bid, ask, covered = b.depth_within(0.02)  # ±2 % of 100 → 98..102
    assert (bid, ask, covered) == (3.0, 4.0, True)
    assert b.depth_within(0.2)[2] is False  # 80..120 exceeds the snapshot depth (90 / 110)


def test_binance_message_parsing():
    e = DepthEvent.from_binance({"e": "depthUpdate", "E": 5, "U": 1, "u": 2, "b": [["1.5", "2"]], "a": []})
    assert (e.first_id, e.final_id, e.bids, e.event_ms) == (1, 2, ((1.5, 2.0),), 5)
    t = AggTrade.from_binance({"a": 9, "p": "100", "q": "0.5", "T": 7, "m": True})
    assert t.buyer_is_aggressor is False  # buyer is maker → seller aggressed


# --- trades --------------------------------------------------------------------------------------


def _t(i, price=100.0, qty=1.0, ms=T0, buy=True):
    return AggTrade(agg_id=i, price=price, qty=qty, trade_ms=ms, buyer_is_aggressor=buy)


def test_trade_duplicates_ignored_and_gaps_reported():
    tr = TradeTracker()
    assert tr.accept(_t(1)) == (True, None)
    assert tr.accept(_t(1)) == (False, None) and tr.duplicates == 1
    keep, gap = tr.accept(_t(5))
    assert keep and (gap.from_id, gap.to_id) == (2, 4)


# --- aggregate -----------------------------------------------------------------------------------


def _synced_book():
    b = LocalBook("BTCUSDT")
    b.on_event(ev(101, 101))
    b.apply_snapshot(SNAP)
    return b


def test_minute_row_synced_levels_trades_and_delta():
    agg = MinuteAggregator("BTCUSDT", bucket_width=1.0, range_pct=0.05)
    b = _synced_book()
    for s in range(60):
        b.on_alive(T0 + s * 1000)
        agg.sample(b, T0 + s * 1000)
    agg.add_trade(_t(1, price=101.2, qty=2.0, ms=T0 + 5000, buy=True))
    agg.add_trade(_t(2, price=99.4, qty=0.5, ms=T0 + 6000, buy=False))
    assert agg.finalize(T0 + 61_000) == []  # grace period not over
    (row,) = agg.finalize(T0 + 62_001)
    assert row["t"] == T0 // 1000 and row["book_state"] == "SYNCED" and row["samples"]["SYNCED"] == 60
    assert row["trades"]["delta"] == 1.5 and row["trades"]["n"] == 2
    assert row["trades"]["by_bucket"] == [[99.0, 0.0, 0.5], [101.0, 2.0, 0.0]]
    levels = {lv[0]: (lv[1], lv[2]) for lv in row["levels"]}
    assert levels[99.0] == (1.0, 0.0) and levels[101.0] == (0.0, 1.0)
    assert round(row["spread_bps_mean"], 4) == round(2 / 100 * 1e4, 4)
    # a trade arriving after its minute was written is counted late, not inserted
    assert agg.add_trade(_t(3, ms=T0 + 10_000)) is False and agg.late_trades == 1


def test_minute_without_synced_book_is_not_an_empty_book():
    agg = MinuteAggregator("BTCUSDT", bucket_width=1.0)
    b = LocalBook("BTCUSDT")  # never synced
    for s in range(60):
        agg.sample(b, T0 + s * 1000)
    (row,) = agg.finalize(T0 + 63_000)
    assert row["book_state"] == "UNAVAILABLE" and row["levels"] == [] and row["mid_last"] is None


# --- storage + session ---------------------------------------------------------------------------


class _Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def _session(tmp_path, clock, snapshots, trades_rest=None):
    cfg = CollectorConfig(symbol="BTCUSDT", data_dir=tmp_path, bucket_width=1.0)
    snaps = list(snapshots)
    return SymbolSession(
        cfg,
        fetch_snapshot=lambda: snaps.pop(0) if snaps else (_ for _ in ()).throw(RuntimeError("no snapshot")),
        fetch_agg_trades=lambda from_id: list(trades_rest or []),
        clock_ms=clock,
    )


def _depth(U, u, b=(), a=()):
    return json.dumps({"stream": "btcusdt@depth@100ms",
                       "data": {"e": "depthUpdate", "E": 1, "U": U, "u": u, "b": list(b), "a": list(a)}})


def _trade(i, p="100.5", q="1", T=T0, m=False):
    return json.dumps({"stream": "btcusdt@aggTrade", "data": {"e": "aggTrade", "a": i, "p": p, "q": q, "T": T, "m": m}})


def test_session_end_to_end_writes_raw_agg_and_status(tmp_path):
    clock = _Clock(T0)
    s = _session(tmp_path, clock, [SNAP], trades_rest=[{"a": 2, "p": "100", "q": "0.25", "T": T0 + 1, "m": True}])
    s.on_connect()
    s.on_message(_depth(101, 101))
    assert s.needs_snapshot()
    s.apply_snapshot()
    assert s.book.state == BookState.SYNCED
    s.on_message(_trade(1))
    s.on_message(_trade(3))  # gap on id 2 → backfilled from REST
    s.on_message(_trade(3))  # duplicate
    for sec in range(0, 63):
        clock.t = T0 + sec * 1000
        s.on_message(_depth(102 + sec, 102 + sec))
        s.tick()
    s.close()
    row = read_minutes(tmp_path, "BTCUSDT", T0 // 1000, T0 // 1000 + 60)[0]
    assert row["book_state"] == "SYNCED" and row["trades"]["n"] == 3 and row["trade_gaps"] == 0
    assert latest_minute(tmp_path, "BTCUSDT", T0 // 1000 + 3600)["t"] == T0 // 1000
    st = read_status(tmp_path, "BTCUSDT")
    assert st["state"] == "SYNCED" and st["trade_duplicates"] == 1 and st["venue"] == "binance-spot"
    raw = list(iter_ndjson(next((tmp_path / "raw" / "BTCUSDT").glob("*.ndjson.gz"))))
    kinds = [r["k"] for r in raw]
    assert kinds[0] == "conn" and "s" in kinds and "gap" in kinds
    gap = next(r for r in raw if r["k"] == "gap")
    assert (gap["from"], gap["to"], gap["filled"], gap["missing"]) == (2, 2, 1, 0)
    assert all("rx" in r for r in raw)


def test_session_snapshot_failure_backs_off_and_disconnect_resets(tmp_path):
    clock = _Clock(T0)
    s = _session(tmp_path, clock, [])
    s.on_connect()
    s.on_message(_depth(101, 101))
    s.apply_snapshot()  # fails
    assert s.snapshot_errors == 1 and not s.needs_snapshot()  # back-off: no hammering of the REST API
    clock.t = T0 + 2001
    assert s.needs_snapshot()
    s.on_disconnect("ConnectionClosed")
    assert s.book.state == BookState.UNAVAILABLE and read_status(tmp_path, "BTCUSDT")["disconnects"] == 1
    s.close()


def test_truncated_gzip_tail_is_tolerated_and_retention(tmp_path):
    p = tmp_path / "raw" / "BTCUSDT"
    p.mkdir(parents=True)
    f = p / "2020-01-01.ndjson.gz"
    with gzip.open(f, "wt") as fh:
        fh.write('{"k":"t","a":1}\n')
    data = f.read_bytes()
    f.write_bytes(data + data[:12])  # second, truncated gzip member
    assert [r["a"] for r in iter_ndjson(f)] == [1]
    assert purge_older_than(tmp_path, "raw", 7, now_ms=T0) == 1 and not f.exists()


# --- engine side: API + agent facts --------------------------------------------------------------


def _collected(tmp_path, clock):
    s = _session(tmp_path, clock, [SNAP])
    s.on_connect()
    s.on_message(_depth(101, 101))
    s.apply_snapshot()
    s.on_message(_trade(1, q="2", m=False))
    for sec in range(0, 63):
        clock.t = T0 + sec * 1000
        s.on_message(_depth(102 + sec, 102 + sec))
        s.tick()
    s.write_status(force=True)
    s.close()


def test_api_status_and_minutes(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app

    clock = _Clock(T0)
    _collected(tmp_path, clock)
    monkeypatch.setattr(settings, "ob_data_dir", str(tmp_path))
    client = TestClient(app)
    P = settings.engine_api_prefix
    st = client.get(f"{P}/orderbook/status").json()
    # status written at T0+62 s, read "now" (real clock) → collector considered down: STALE, not frozen SYNCED
    assert st["enabled"] is True and st["symbols"]["BTCUSDT"]["state"] == "STALE"
    assert st["symbols"]["BTCUSDT"]["reason"] == "collector_down"
    body = client.get(f"{P}/orderbook/BTCUSDT/minutes",
                      params={"from": T0 // 1000, "to": T0 // 1000 + 180}).json()
    assert body["n_rows"] == 1 and body["missing_minutes"] == 2 and body["states"]["SYNCED"] == 1
    assert client.get(f"{P}/orderbook/BTCUSDT/minutes", params={"from": 10, "to": 5}).status_code == 422


def test_factsheet_orderbook_facts(tmp_path):
    from app.agents.factsheet import facts_from_orderbook
    from app.microstructure.book import read as ob_read
    from app.microstructure.book.storage import read_status

    clock = _Clock(T0)
    _collected(tmp_path, clock)
    now_s = T0 // 1000 + 65
    status = ob_read.effective_status(read_status(tmp_path, "BTCUSDT"), now_s)
    assert status["collector_alive"] is True
    minute = ob_read.latest(tmp_path, "BTCUSDT", now_s)
    facts = {f["id"]: f for f in facts_from_orderbook(status, minute)}
    assert facts["ob.state"]["value"] == "SYNCED" and facts["ob.state"]["source"] == "binance-spot"
    assert facts["ob.minute.aggressor_delta"]["value"] == 2.0
    assert facts["ob.minute.spread_pct"]["unit"] == "%"
    assert facts["ob.minute.depth_10bp_bid"]["timeframe"] == "1m"
    none = facts_from_orderbook(None, None)
    assert none[0]["status"] == "unavailable" and none[0]["reason"] == "not_collected"


def test_quality_counts_missing_minutes_as_not_measured(tmp_path):
    from app.microstructure.book import read as ob_read

    clock = _Clock(T0)
    _collected(tmp_path, clock)
    q = ob_read.quality(tmp_path, "BTCUSDT", hours=1, now_s=T0 // 1000 + 120)
    assert q["expected_minutes"] == 60 and q["written_minutes"] == 1 and q["missing_minutes"] == 59
    assert q["states"]["SYNCED"] == 1 and q["synced_pct"] == round(100 / 60, 2)
    assert q["spread_bps_median"] is not None and q["status"]["collector_alive"] is False
