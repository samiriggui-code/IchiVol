"""2026-09-28: viewing or refreshing the screener (UI / agent channel, any timeframe) never drives the paper
portfolio. Only the background loop on the default timeframe feeds the automatic 1h strategy."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.paper import engine as paper_engine
from app.screener import cache as cache_module
from app.screener.cache import ScreenerCache, screener_cache
from app.screener.service import ScreenerRow


def _rows(symbols, timeframe="1h", limit=300):
    return [
        ScreenerRow(symbol="BTCUSDT", exchange="binance", timeframe=timeframe, price=1.0, candles=[],
                    ichimoku=None, rvol=None, decision=None, pipeline=None)
    ]


@pytest.fixture
def paper_calls(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(cache_module, "scan_watchlist", _rows)
    monkeypatch.setattr(cache_module, "persist_scan", lambda session, row: None)
    monkeypatch.setattr(cache_module, "record_signal_evidence", lambda session, row: None)
    from app.agent_channel import commands
    from app.api import market

    monkeypatch.setattr(market, "summary_dict", lambda row: {"symbol": row.symbol})
    monkeypatch.setattr(commands, "summary_dict", lambda row: {"symbol": row.symbol})
    monkeypatch.setattr(
        paper_engine, "sync_auto_watchlist",
        lambda session, rows: calls.extend(r.timeframe for r in rows) or [],
    )
    return calls


@pytest.mark.parametrize("tf", ["15m", "1h", "4h", "1d"])
def test_screener_route_force_refresh_never_syncs_paper(paper_calls, tf):
    resp = TestClient(app).get("/api/engine/screener", params={"timeframe": tf, "force": "true"})
    assert resp.status_code == 200
    assert paper_calls == []


@pytest.mark.parametrize("tf", ["15m", "1h", "4h", "1d"])
def test_direct_refresh_without_paper_sync_flag_never_syncs(paper_calls, tf):
    ScreenerCache(refresh_interval_s=999, default_timeframe="1h").refresh(timeframe=tf, persist=True)
    assert paper_calls == []


def test_background_loop_flag_syncs_default_timeframe_only(paper_calls, monkeypatch):
    from app.screener import cache as cache_mod

    # Baseline scope only: the wide-universe extra scan (parallel account) is covered elsewhere.
    monkeypatch.setattr(cache_mod, "wide_universe_wanted", lambda: False)
    c = ScreenerCache(refresh_interval_s=999, default_timeframe="1h")
    c.refresh(timeframe="15m", paper_sync=True)
    c.refresh(timeframe="4h", paper_sync=True)
    assert paper_calls == []
    c.refresh(paper_sync=True)
    assert paper_calls == ["1h"]


def test_agent_channel_screener_command_never_syncs(paper_calls):
    from app.agent_channel import commands

    commands.cmd_scan_market({"timeframe": "4h", "force": True})
    commands.cmd_scan_market({"timeframe": "1h", "force": True})
    assert paper_calls == []


def test_engine_ignores_rows_outside_auto_timeframes(monkeypatch):
    """Defense in depth: even if a caller passes 15m/4h rows, the portfolio neither opens nor manages positions."""
    pf = SimpleNamespace(id="pf", code="ICHIVOL_BASELINE_V1", strategy_profile={"auto_timeframes": ["1h"]})
    monkeypatch.setattr(paper_engine, "ensure_syncable_portfolios", lambda session: [pf])
    synced: list[str] = []
    monkeypatch.setattr(paper_engine, "sync_position", lambda session, **kw: synced.append(kw["timeframe"]))
    monkeypatch.setattr(paper_engine.shadow_broker, "mark_shadows", lambda session, marks: None)
    monkeypatch.setattr(paper_engine.paper_broker, "snapshot_equity", lambda session, portfolio, marks: None)
    passthrough = lambda pipeline, *a, **k: SimpleNamespace(  # noqa: E731
        pipeline=pipeline, blocked=False, raw_decision=None, reason=None,
        structure_payload=None, fibonacci_payload=None, context_payload=None)
    monkeypatch.setattr(paper_engine, "apply_structure_gate", passthrough)
    monkeypatch.setattr(paper_engine, "apply_fibonacci_gate", passthrough)
    monkeypatch.setattr(paper_engine, "apply_context_gate", passthrough)

    class _S:
        def commit(self):
            pass

    rows = [SimpleNamespace(symbol="BTCUSDT", timeframe=tf, price=1.0, candles=[], atr=None, rvol=None,
                            pipeline=SimpleNamespace(decision="BUY"), signal_timing=None)
            for tf in ("15m", "1h", "4h", "1d")]
    paper_engine.sync_auto_watchlist(_S(), rows)
    assert synced == ["1h"]


def test_profile_declares_auto_timeframes_and_missing_key_means_1h():
    from app.paper.strategy_profiles import BASELINE_PROFILE

    assert BASELINE_PROFILE["auto_timeframes"] == ["1h"]
    assert paper_engine.auto_timeframes({}) == ("1h",)
    assert paper_engine.auto_timeframes({"auto_timeframes": ["1h", "4h"]}) == ("1h", "4h")


def test_module_singleton_is_the_one_the_route_uses():
    from app.api import market

    assert market.screener_cache is screener_cache
