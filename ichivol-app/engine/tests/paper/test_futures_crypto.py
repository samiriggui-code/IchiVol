"""Futures & Crypto portfolio (YM, MGC, BTC configurable): its own markets only, the shared accounts never see
them, global open-risk cap. (2026-10-27 : le compte est retiré, sa vue API et son réglage BTC aussi ; YM rejoint
le portefeuille unique. Le module et son profil restent, testés ici comme définitions.)"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from app.agents.types import Direction
from app.db.session import engine
from app.decision.pipeline import PipelineResult
from app.paper import engine as paper
from app.paper import futures_crypto as fc
from app.paper.risk_kernel import OpenLotSnap, OpenPlan, PortfolioState, evaluate, market_state_from_profile
from app.paper.strategy_profiles import ALL_PROFILES, BASELINE_PROFILE, profile_for
from app.universe.catalog import dedicated_only_ids, default_watchlist, get_instrument

try:
    with engine.connect():
        pass
    DB_AVAILABLE = True
except OperationalError:
    DB_AVAILABLE = False

db = pytest.mark.skipif(not DB_AVAILABLE, reason="ichivol_engine_dev Postgres not reachable")


def test_three_markets_and_btc_modes():
    p = profile_for(fc.FUTURES_CRYPTO_CODE)
    assert fc.traded_symbols(p) == ["YM", "MGC", "BTCUSDT"]
    assert fc.traded_symbols(fc.with_btc_mode(p, "perpetual")) == ["YM", "MGC", "BTCPERP"]
    assert fc.traded_symbols(fc.with_btc_mode(p, "cme")) == ["YM", "MGC", "BTCCME"]
    assert fc.btc_mode({"btc_mode": "nonsense"}) == "spot"
    with pytest.raises(ValueError):
        fc.with_btc_mode(p, "options")


def test_instruments_resolve_to_real_feeds_and_stay_out_of_the_shared_watchlist():
    assert get_instrument("YM").provider_symbol == "US30"
    assert get_instrument("MGC").provider_symbol == "XAUUSD"
    assert get_instrument("BTCPERP").provider == "binance_usdm"
    assert get_instrument("BTCCME").provider_symbol == "BTCUSDT"
    assert dedicated_only_ids() == {"YM", "MGC", "BTCPERP", "BTCCME"}
    assert not (set(default_watchlist()) & dedicated_only_ids())


def test_contracts_use_cme_sizes():
    assert fc.contracts_for("YM", 10.0) == 2.0  # 5 $ per point
    assert fc.contracts_for("MGC", 5.0) == 0.5  # 10 oz
    assert fc.contracts_for("BTCCME", 0.25) == 2.5  # MBT = 0.1 BTC
    assert fc.contracts_for("ETHUSDT", 1.0) is None


def test_baseline_profile_is_untouched():
    assert "dedicated_markets" not in BASELINE_PROFILE
    assert "btc_mode" not in BASELINE_PROFILE
    assert "YM" not in BASELINE_PROFILE["friction_bps_by_symbol"]
    assert ALL_PROFILES[fc.FUTURES_CRYPTO_CODE]["max_open_risk_pct"] == 0.01


def test_each_account_only_trades_its_own_markets():
    fut = profile_for(fc.FUTURES_CRYPTO_CODE)
    for sym in ("YM", "MGC", "BTCUSDT"):
        assert paper.trades_symbol(fut, sym)
    for sym in ("ETHUSDT", "XAUUSD", "BTCPERP"):
        assert not paper.trades_symbol(fut, sym)
    base = dict(BASELINE_PROFILE)
    for sym in ("YM", "MGC", "BTCPERP", "BTCCME"):
        assert not paper.trades_symbol(base, sym)
    assert paper.trades_symbol(base, "BTCUSDT") and paper.trades_symbol(base, "XAUUSD")


def test_auto_sync_routes_rows_by_portfolio(monkeypatch):
    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(paper, "sync_position", lambda session, **kw: seen.append(
        (kw["signal_extra"]["portfolio_code"], kw["symbol"])))
    monkeypatch.setattr(paper, "ensure_syncable_portfolios", lambda session: [
        SimpleNamespace(id="a", code="BASE", strategy_profile={"auto_timeframes": ["1h"]}),
        SimpleNamespace(id="b", code="FUT", strategy_profile=profile_for(fc.FUTURES_CRYPTO_CODE)),
    ])
    monkeypatch.setattr(paper.shadow_broker, "mark_shadows", lambda *a, **k: None)
    monkeypatch.setattr(paper.paper_broker, "snapshot_equity", lambda *a, **k: None)

    def _row(symbol):
        return SimpleNamespace(
            symbol=symbol, timeframe="1h", price=100.0,
            pipeline=PipelineResult(decision="BUY", direction=Direction.LONG, stages=[]),
            atr=SimpleNamespace(suggested_stop_distance=2.0), candles=[], rvol=None, mtf_matrix=None,
            signal_timing=None,
        )

    fc.clear_signals()
    paper.sync_auto_watchlist(SimpleNamespace(commit=lambda: None), [_row(s) for s in ("BTCUSDT", "ETHUSDT", "YM", "MGC")])
    assert seen == [("BASE", "BTCUSDT"), ("FUT", "BTCUSDT"), ("BASE", "ETHUSDT"), ("FUT", "YM"), ("FUT", "MGC")]
    # The verdict this portfolio acted on is kept per market for its view (pipeline gate, not the combiner).
    ym = fc.last_signal("YM")
    assert ym["decision"] == "BUY" and ym["direction"] == "LONG" and ym["price"] == 100.0
    assert fc.last_signal("ETHUSDT") is None


def test_global_open_risk_cap_refuses_a_third_full_risk_position():
    p = profile_for(fc.FUTURES_CRYPTO_CODE)
    equity = 5000.0
    full = equity * p["risk_pct"]  # 25 €
    plan = OpenPlan(symbol="MGC", timeframe="1h", direction="LONG", price=1000.0, stop_distance=50.0)

    def _state(opens):
        return PortfolioState(cash=equity, equity=equity, profile=p, open_positions=tuple(opens),
                              day_start_equity=equity)

    one = [OpenLotSnap(symbol="YM", notional=1000.0, risk_amount=full)]
    assert evaluate(plan, _state(one), market_state_from_profile(p, "MGC")).accepted
    two = one + [OpenLotSnap(symbol="BTCUSDT", notional=1000.0, risk_amount=full)]
    refused = evaluate(plan, _state(two), market_state_from_profile(p, "MGC"))
    assert not refused.accepted and refused.primary_code() == "open_risk_cap"


def test_cache_scans_dedicated_markets_only_on_the_background_paper_cycle(monkeypatch):
    from app.screener import cache as cache_module
    from app.screener.service import ScreenerRow

    scanned: list[list[str]] = []
    fed: list[list[str]] = []

    def _scan(symbols, timeframe="1h", limit=300):
        scanned.append(list(symbols))
        return [ScreenerRow(symbol=s, exchange="biquote", timeframe=timeframe, price=1.0, candles=[],
                            ichimoku=None, rvol=None, decision=None, pipeline=None) for s in symbols[:1]]

    monkeypatch.setattr(cache_module, "scan_watchlist", _scan)
    monkeypatch.setattr(cache_module, "persist_scan", lambda session, row: None)
    monkeypatch.setattr(cache_module, "record_signal_evidence", lambda session, row: None)
    monkeypatch.setattr(cache_module, "dedicated_extra_symbols", lambda: ["YM", "MGC"])
    monkeypatch.setattr(paper, "sync_auto_watchlist", lambda session, rows: fed.append([r.symbol for r in rows]) or [])

    c = cache_module.ScreenerCache(refresh_interval_s=999, default_timeframe="1h")
    c.refresh(persist=True)
    assert scanned == [list(cache_module.DEFAULT_WATCHLIST)] and fed == []
    scanned.clear()
    entry = c.refresh(persist=True, paper_sync=True)
    assert scanned[1] == ["YM", "MGC"]
    assert fed == [[cache_module.DEFAULT_WATCHLIST[0], "YM"]]
    assert [r.symbol for r in entry.rows] == [cache_module.DEFAULT_WATCHLIST[0]]  # screener cache unchanged
