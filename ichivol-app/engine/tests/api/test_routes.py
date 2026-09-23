from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api import decisions as decisions_routes
from app.api import market as market_routes
from app.api import paper as paper_routes
from app.api import paper_orders as paper_orders_routes
from app.api import routes
from app.db.session import engine as db_engine
from app.indicators.ichimoku import Candle
from app.main import app
from app.market_data import binance, binance_futures
from app.screener import cache as cache_module

client = TestClient(app)

try:
    with db_engine.connect():
        pass
    DB_AVAILABLE = True
except OperationalError:
    DB_AVAILABLE = False

# Paper routes hit the real ichivol_engine_dev Postgres (same convention as
# tests/paper/test_engine.py). Skip when unreachable so CI/local without DB
# still get a green suite for the pure route/shape tests above.
requires_db = pytest.mark.skipif(
    not DB_AVAILABLE, reason="ichivol_engine_dev Postgres not reachable"
)


@pytest.fixture(autouse=True)
def _no_live_oi_funding_calls(monkeypatch):
    # /decisions and /screener now also fetch OI/Funding for Binance-backed
    # symbols (app/indicators/oi_funding.py, V2) -- these route tests only
    # mock OHLCV (binance.fetch_klines) and must stay network-free.
    monkeypatch.setattr(binance_futures, "fetch_open_interest_hist", lambda *a, **k: [])
    monkeypatch.setattr(binance_futures, "fetch_funding_rate_hist", lambda *a, **k: [])


@pytest.fixture(autouse=True)
def _no_contamination_of_the_real_paper_portfolio(monkeypatch):
    # Real bug found live (2026-09-16): test_screener_endpoint_shape mocks
    # binance.fetch_klines with a synthetic fixture and forces a cold cache
    # refresh -- ScreenerCache.refresh() runs for the REAL DEFAULT_WATCHLIST
    # against this fake data and (since app/screener/cache.py wires
    # app/paper/engine.py::sync_auto_watchlist into that same refresh)
    # closed several real open positions in the production `paper_positions`
    # table at the fixture's fake price (259.5), corrupting real PnL data.
    # Every test in this module hits the real `app.main.app` + real DB, so
    # this is blanket, not per-test: paper sync never runs from here.
    monkeypatch.setattr(cache_module.paper_engine, "sync_auto_watchlist", lambda session, rows: [])


def _uptrend_with_spike(n: int) -> list[Candle]:
    volumes = [50.0] * (n - 1) + [250.0]
    return [
        Candle(time=i, open=100 + i, high=101 + i, low=99 + i, close=100.5 + i, volume=volumes[i])
        for i in range(n)
    ]


def test_health_endpoint():
    resp = client.get("/api/engine/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "ichivol-engine"}


def test_universe_endpoint_shape():
    resp = client.get("/api/engine/universe")
    assert resp.status_code == 200
    body = resp.json()

    assert "crypto" in body["classes"]
    assert "forex" in body["classes"]

    by_id = {i["id"]: i for i in body["instruments"]}
    assert by_id["BTCUSDT"]["wired"] is True
    assert by_id["BTCUSDT"]["provider"] == "binance"
    # Forex/metal/index/energy moved to biquote (Phase 1c, free/keyless)
    # since Twelve Data's free tier gates several of these behind a paid
    # plan (see app/universe/catalog.py) -- Twelve Data now only backs the
    # two equities (AAPL/TSLA), where its real exchange volume matters.
    assert by_id["EURUSD"]["wired"] is True
    assert by_id["EURUSD"]["provider"] == "biquote"
    assert by_id["EURUSD"]["asset_class"] == "forex"
    assert by_id["WTI"]["wired"] is True
    assert by_id["WTI"]["provider"] == "biquote"
    assert by_id["AAPL"]["wired"] is True
    assert by_id["AAPL"]["provider"] == "twelve_data"


def test_decision_endpoint_shape(monkeypatch):
    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)

    resp = client.get("/api/engine/decisions/BTCUSDT", params={"persist": "false"})
    assert resp.status_code == 200
    body = resp.json()

    for field in (
        "symbol", "timeframe", "decision", "confidence", "ichimoku_score", "rvol",
        "reasons", "risks", "invalidation", "timestamp", "direction", "probability", "price",
    ):
        assert field in body, f"missing field {field!r} in decision response"

    assert body["symbol"] == "BTCUSDT"
    assert body["decision"] == "STRONG_BUY"
    assert body["timestamp"] == candles[-1].time


def test_decision_endpoint_404_on_insufficient_history(monkeypatch):
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: [])

    resp = client.get("/api/engine/decisions/BTCUSDT", params={"persist": "false"})
    assert resp.status_code == 404


def test_decision_endpoint_404_on_unwired_instrument(monkeypatch):
    # Every real catalog entry is wired now (crypto -> binance, equities ->
    # twelve_data, everything else -> biquote, see app/universe/catalog.py),
    # so this injects its own bare placeholder rather than depending on some
    # business instrument happening to still be unwired -- same approach as
    # tests/market_data/test_resolve.py.
    import app.market_data.resolve as resolve_module
    from app.universe.types import AssetClass, Instrument

    placeholder = Instrument(
        id="STILL_UNWIRED",
        asset_class=AssetClass.ENERGY,
        label="Still Unwired",
        provider=None,
        provider_symbol=None,
    )
    monkeypatch.setattr(
        resolve_module,
        "get_instrument",
        lambda symbol_or_id: placeholder if symbol_or_id == "STILL_UNWIRED" else None,
    )

    resp = client.get("/api/engine/decisions/STILL_UNWIRED", params={"persist": "false"})
    assert resp.status_code == 404
    assert "provider_not_wired" in resp.json()["detail"]


def test_screener_endpoint_shape(monkeypatch):
    import app.screener.cache as cache_module

    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)
    # This test only cares about the JSON shape, not persistence (covered
    # separately in tests/screener/test_cache.py) -- don't touch the real DB.
    monkeypatch.setattr(cache_module, "persist_scan", lambda session, row: None)
    cache_module.screener_cache._entry = None  # force a cold recompute

    resp = client.get("/api/engine/screener")
    assert resp.status_code == 200
    body = resp.json()
    assert "rows" in body
    assert "computed_at" in body
    assert "cache_age_seconds" in body
    assert len(body["rows"]) > 0
    for field in ("symbol", "decision", "confidence", "ichimoku_score", "rvol", "price", "risk"):
        assert field in body["rows"][0]
    # risk is the machine-readable stop-distance hint a caller (paper
    # trading today, any future broker) needs to act -- see
    # docs/HANDOFF-CURSOR-PIPELINE-NATIVE.md §14.
    risk = body["rows"][0]["risk"]
    assert risk is not None
    for field in ("atr", "regime", "suggested_stop_distance"):
        assert field in risk


def test_backtest_endpoint_shape(monkeypatch):
    candles = _uptrend_with_spike(300)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)

    resp = client.get("/api/engine/backtest/BTCUSDT", params={"limit": 300})
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "BTCUSDT"
    assert set(body["experiments"]) == {
        "ICHIMOKU_ONLY",
        "ICHIMOKU_RVOL",
        "ICHIMOKU_RVOL_ENTRY_GATE",
        "PIPELINE",
        "PIPELINE_WYCKOFF_FILTER",
    }
    for exp in body["experiments"].values():
        for field in ("total_return", "sharpe", "max_drawdown", "num_trades", "exposure"):
            assert field in exp["metrics"]
        assert "trades" in exp["backtest"]


def test_backtest_endpoint_404_on_insufficient_history(monkeypatch):
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: [])
    resp = client.get("/api/engine/backtest/BTCUSDT")
    assert resp.status_code == 404


def test_decision_endpoint_accepts_rvol_and_atr_threshold_overrides(monkeypatch):
    # CDC V1 "Seuils RVOL/ATR configurables Settings" -- a caller-supplied
    # threshold set must actually be accepted and used, not just tolerated.
    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)

    resp = client.get(
        "/api/engine/decisions/BTCUSDT",
        params={
            "persist": "false",
            "rvol_low": 0.5,
            "rvol_significant": 1.0,
            "rvol_strong": 2.0,
            "rvol_anomaly": 100.0,  # far above the fixture's actual RVOL
            "atr_dead_percentile": 0.1,
            "atr_extreme_percentile": 0.8,
            "atr_stop_multiplier": 2.0,
        },
    )
    assert resp.status_code == 200
    # With anomaly_threshold=100.0 the fixture's real RVOL can't clear it,
    # so this should not report ANOMALY the way the default-threshold test
    # (test_decision_endpoint_shape) implicitly allows.
    assert resp.json()["rvol_detail"]["metadata"]["anomaly_level"] != "ANOMALY"


def test_decision_endpoint_rejects_out_of_order_rvol_thresholds():
    resp = client.get(
        "/api/engine/decisions/BTCUSDT",
        params={"persist": "false", "rvol_low": 2.0, "rvol_significant": 1.0},
    )
    assert resp.status_code == 422
    assert "invalid_rvol_thresholds" in resp.json()["detail"]


def test_decision_endpoint_rejects_out_of_order_atr_percentiles():
    resp = client.get(
        "/api/engine/decisions/BTCUSDT",
        params={"persist": "false", "atr_dead_percentile": 0.9, "atr_extreme_percentile": 0.1},
    )
    assert resp.status_code == 422
    assert "invalid_atr_percentiles" in resp.json()["detail"]


def test_decision_endpoint_forwards_the_twelve_data_key_header(monkeypatch):
    # Unit-level coverage for the ContextVar itself lives in
    # tests/market_data/test_twelve_data.py -- this proves the *route*
    # actually reads `X-Twelve-Data-Key` and gets it all the way down to
    # the outbound HTTP call, through resolve_and_fetch -> TwelveDataProvider.
    from datetime import datetime, timedelta

    from app.market_data import twelve_data

    twelve_data._cache.clear()  # a prior test's 90s-TTL cache entry would hide this call entirely
    candles = _uptrend_with_spike(160)
    captured_keys: list[str | None] = []

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            base = datetime(2024, 1, 1)
            return {
                "status": "ok",
                "values": [
                    {
                        "datetime": (base + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"),
                        "open": str(c.open), "high": str(c.high), "low": str(c.low),
                        "close": str(c.close), "volume": str(c.volume),
                    }
                    for i, c in enumerate(candles)
                ],
            }

    def fake_get(url, params=None, **kwargs):
        captured_keys.append((params or {}).get("apikey"))
        return FakeResp()

    monkeypatch.setattr(twelve_data.httpx, "get", fake_get)

    resp = client.get(
        "/api/engine/decisions/AAPL",
        params={"persist": "false"},
        headers={"X-Twelve-Data-Key": "clients-own-key"},
    )
    assert resp.status_code == 200
    assert captured_keys, "expected at least one outbound Twelve Data call"
    assert all(k == "clients-own-key" for k in captured_keys)


def test_ohlcv_endpoint_forwards_the_twelve_data_key_header(monkeypatch):
    from datetime import datetime, timedelta

    from app.market_data import twelve_data

    twelve_data._cache.clear()
    candles = _uptrend_with_spike(5)
    captured_keys: list[str | None] = []

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            base = datetime(2024, 1, 1)
            return {
                "status": "ok",
                "values": [
                    {
                        "datetime": (base + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"),
                        "open": str(c.open), "high": str(c.high), "low": str(c.low),
                        "close": str(c.close), "volume": str(c.volume),
                    }
                    for i, c in enumerate(candles)
                ],
            }

    def fake_get(url, params=None, **kwargs):
        captured_keys.append((params or {}).get("apikey"))
        return FakeResp()

    monkeypatch.setattr(twelve_data.httpx, "get", fake_get)

    resp = client.get(
        "/api/engine/ohlcv/AAPL", headers={"X-Twelve-Data-Key": "another-clients-key"}
    )
    assert resp.status_code == 200
    assert captured_keys, "expected at least one outbound Twelve Data call"
    assert all(k == "another-clients-key" for k in captured_keys)


def test_decision_endpoint_without_the_header_uses_the_operator_key(monkeypatch):
    # No X-Twelve-Data-Key sent at all -- must fall back to the operator's
    # own TWELVE_DATA_API_KEY (engine/.env), never fail or send `None`.
    from datetime import datetime, timedelta

    from app.market_data import twelve_data

    twelve_data._cache.clear()
    candles = _uptrend_with_spike(160)
    captured_keys: list[str | None] = []

    monkeypatch.setattr(twelve_data.settings, "twelve_data_api_key", "operator-key")

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            base = datetime(2024, 1, 1)
            return {
                "status": "ok",
                "values": [
                    {
                        "datetime": (base + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"),
                        "open": str(c.open), "high": str(c.high), "low": str(c.low),
                        "close": str(c.close), "volume": str(c.volume),
                    }
                    for i, c in enumerate(candles)
                ],
            }

    def fake_get(url, params=None, **kwargs):
        captured_keys.append((params or {}).get("apikey"))
        return FakeResp()

    monkeypatch.setattr(twelve_data.httpx, "get", fake_get)

    resp = client.get("/api/engine/decisions/AAPL", params={"persist": "false"})
    assert resp.status_code == 200
    assert captured_keys
    assert all(k == "operator-key" for k in captured_keys)


@requires_db
def test_list_paper_positions_endpoint_shape():
    resp = client.get("/api/engine/paper/positions")
    assert resp.status_code == 200
    body = resp.json()
    assert "positions" in body
    assert isinstance(body["positions"], list)


@requires_db
def test_paper_performance_endpoint_shape():
    resp = client.get("/api/engine/paper/performance")
    assert resp.status_code == 200
    body = resp.json()
    for field in (
        "num_closed_trades", "num_open_positions", "total_return", "win_rate",
        "profit_factor", "expectancy", "avg_holding_hours", "best_trade_pct", "worst_trade_pct",
    ):
        assert field in body


@requires_db
def test_open_paper_position_opens_on_an_actionable_decision(monkeypatch):
    # Getting a real 5-gate pipeline to actually resolve to BUY out of a
    # synthetic candle fixture is fragile (Location/Regime routinely FAIL
    # on hand-crafted series) -- this route only needs to prove it wires
    # scan_symbol's result into app/paper/engine.py correctly, which
    # app/paper/test_engine.py already covers in depth. Fake scan_symbol's
    # result directly instead. Baseline require_atr_stop needs a stop stub.
    from types import SimpleNamespace

    from app.agents.types import Direction
    from app.db.models import (
        LedgerLeg,
        LedgerTransaction,
        PaperJournalEvent,
        PaperOrder,
        PaperPosition,
    )
    from app.db.session import SessionLocal
    from app.decision.pipeline import PipelineResult
    from app.screener.service import ScreenerRow

    fake_pipeline = PipelineResult(decision="BUY", direction=Direction.LONG, stages=[])
    fake_row = ScreenerRow(
        symbol="BTCUSDT", exchange="binance", timeframe="1h", price=12345.0,
        candles=[], ichimoku=None, rvol=None, decision=None, pipeline=fake_pipeline,
        atr=SimpleNamespace(suggested_stop_distance=200.0),
    )
    monkeypatch.setattr(routes, "scan_symbol", lambda symbol, timeframe="1h", **k: fake_row)

    monkeypatch.setattr(decisions_routes, "scan_symbol", lambda symbol, timeframe="1h", **k: fake_row)

    monkeypatch.setattr(paper_routes, "scan_symbol", lambda symbol, timeframe="1h", **k: fake_row)
    monkeypatch.setattr(paper_orders_routes, "scan_symbol", lambda symbol, timeframe="1h", **k: fake_row)

    resp = client.post(
        "/api/engine/paper/positions", params={"symbol": "BTCUSDT", "user_id": "test-user-routes"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["symbol"] == "BTCUSDT"
    assert body["source"] == "user_confirmed"
    assert body["user_id"] == "test-user-routes"
    assert body["status"] == "OPEN"
    assert body["direction"] in ("LONG", "SHORT")

    # Idempotent: a second call for the same user/symbol returns the same
    # position rather than opening a duplicate.
    resp2 = client.post(
        "/api/engine/paper/positions", params={"symbol": "BTCUSDT", "user_id": "test-user-routes"}
    )
    assert resp2.status_code == 200
    assert resp2.json()["id"] == body["id"]

    close_resp = client.post(f"/api/engine/paper/positions/{body['id']}/close")
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "CLOSED"

    # Hard-delete, not just close: this row's fake price (12345.0) would
    # otherwise sit in the *real* paper_positions table forever, skewing
    # GET /paper/performance's aggregate stats -- these tests share the
    # real ichivol_engine_dev DB, there's no separate test database.
    from app.db.models import PaperPortfolio
    from app.paper.strategy_profiles import BASELINE_CODE

    session = SessionLocal()
    try:
        pid = body["id"]
        session.query(PaperJournalEvent).filter_by(position_id=pid).delete()
        tx_ids = [
            t.id for t in session.query(LedgerTransaction).filter_by(ref=pid).all()
        ]
        if tx_ids:
            session.query(LedgerLeg).filter(
                LedgerLeg.transaction_id.in_(tx_ids)
            ).delete(synchronize_session=False)
            session.query(LedgerTransaction).filter(
                LedgerTransaction.id.in_(tx_ids)
            ).delete(synchronize_session=False)
        session.query(PaperOrder).filter_by(position_id=pid).delete()
        session.query(PaperPosition).filter_by(id=pid).delete()
        base = session.query(PaperPortfolio).filter_by(code=BASELINE_CODE).one_or_none()
        if base is not None:
            base.cash = base.initial_cash
            base.realized_pnl = 0.0
        session.commit()
    finally:
        session.close()


@requires_db
def test_open_paper_position_accepts_rvol_and_atr_threshold_overrides(monkeypatch):
    # Feature parity with /decisions/{symbol} and /screener (2026-09-16):
    # this route previously always scanned with default thresholds, so a
    # demo/calibration call under relaxed thresholds couldn't actually open
    # a position -- only inspect a decision. Assert the overrides really
    # reach scan_symbol as RvolParams/AtrParams, not just get accepted and
    # silently dropped.
    from app.indicators.atr import AtrParams
    from app.indicators.rvol import RvolParams

    captured: dict = {}

    def _fake_scan_symbol(symbol, timeframe="1h", **kwargs):
        captured["rvol_params"] = kwargs.get("rvol_params")
        captured["atr_params"] = kwargs.get("atr_params")
        from app.agents.types import Direction
        from app.decision.pipeline import PipelineResult
        from app.screener.service import ScreenerRow

        return ScreenerRow(
            symbol=symbol, exchange="binance", timeframe=timeframe, price=1.0,
            candles=[], ichimoku=None, rvol=None, decision=None,
            pipeline=PipelineResult(decision="WATCH", direction=Direction.LONG, stages=[]),
        )

    monkeypatch.setattr(routes, "scan_symbol", _fake_scan_symbol)


    monkeypatch.setattr(decisions_routes, "scan_symbol", _fake_scan_symbol)


    monkeypatch.setattr(paper_routes, "scan_symbol", _fake_scan_symbol)
    monkeypatch.setattr(paper_orders_routes, "scan_symbol", _fake_scan_symbol)

    resp = client.post(
        "/api/engine/paper/positions",
        params={
            "symbol": "ATOMUSDT", "user_id": "test-user-thresholds",
            "rvol_significant": 0.9,
        },
    )
    # WATCH is still not actionable -- 422 either way; this test only cares
    # that the override reached scan_symbol correctly.
    assert resp.status_code == 422
    assert captured["rvol_params"] == RvolParams(significant_threshold=0.9)
    assert captured["atr_params"] == AtrParams()


@requires_db
def test_open_paper_position_accepts_a_non_crypto_symbol(monkeypatch):
    # Paper multi-classe (docs/CAHIER-DES-CHARGES.md §5 V2, lifted
    # 2026-09-16): a biquote-backed symbol (forex/métal/index/énergie) opens
    # a paper position exactly like a Binance one -- the engine/DB side was
    # already asset-agnostic (PaperPosition has no exchange column), only
    # this route's explicit crypto-only guard blocked it.
    # Baseline is long-only + ATR stop: exercise multi-classe via BUY/LONG.
    from types import SimpleNamespace

    from app.agents.types import Direction
    from app.db.models import (
        LedgerLeg,
        LedgerTransaction,
        PaperJournalEvent,
        PaperOrder,
        PaperPosition,
    )
    from app.db.session import SessionLocal
    from app.decision.pipeline import PipelineResult
    from app.screener.service import ScreenerRow

    fake_pipeline = PipelineResult(decision="BUY", direction=Direction.LONG, stages=[])
    fake_row = ScreenerRow(
        symbol="GBPUSD", exchange="biquote", timeframe="1h", price=1.27,
        candles=[], ichimoku=None, rvol=None, decision=None, pipeline=fake_pipeline,
        atr=SimpleNamespace(suggested_stop_distance=0.01),
    )
    monkeypatch.setattr(routes, "scan_symbol", lambda symbol, timeframe="1h", **k: fake_row)

    monkeypatch.setattr(decisions_routes, "scan_symbol", lambda symbol, timeframe="1h", **k: fake_row)

    monkeypatch.setattr(paper_routes, "scan_symbol", lambda symbol, timeframe="1h", **k: fake_row)
    monkeypatch.setattr(paper_orders_routes, "scan_symbol", lambda symbol, timeframe="1h", **k: fake_row)

    resp = client.post(
        "/api/engine/paper/positions", params={"symbol": "GBPUSD", "user_id": "test-user-routes"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["symbol"] == "GBPUSD"
    assert body["direction"] == "LONG"
    assert body["status"] == "OPEN"

    session = SessionLocal()
    try:
        pid = body["id"]
        session.query(PaperJournalEvent).filter_by(position_id=pid).delete()
        tx_ids = [
            t.id for t in session.query(LedgerTransaction).filter_by(ref=pid).all()
        ]
        if tx_ids:
            session.query(LedgerLeg).filter(
                LedgerLeg.transaction_id.in_(tx_ids)
            ).delete(synchronize_session=False)
            session.query(LedgerTransaction).filter(
                LedgerTransaction.id.in_(tx_ids)
            ).delete(synchronize_session=False)
        session.query(PaperOrder).filter_by(position_id=pid).delete()
        session.query(PaperPosition).filter_by(id=pid).delete()
        from app.db.models import PaperPortfolio
        from app.paper.strategy_profiles import BASELINE_CODE

        base = session.query(PaperPortfolio).filter_by(code=BASELINE_CODE).one_or_none()
        if base is not None:
            base.cash = base.initial_cash
            base.realized_pnl = 0.0
        session.commit()
    finally:
        session.close()


@requires_db
def test_open_paper_position_reports_no_atr_stop_honestly(monkeypatch):
    """BUY without ATR stop must 422 with no_atr_stop, not a fake WATCH message."""
    from app.agents.types import Direction
    from app.decision.pipeline import PipelineResult
    from app.screener.service import ScreenerRow

    fake_pipeline = PipelineResult(decision="BUY", direction=Direction.LONG, stages=[])
    fake_row = ScreenerRow(
        symbol="ETHUSDT", exchange="binance", timeframe="1h", price=3000.0,
        candles=[], ichimoku=None, rvol=None, decision=None, pipeline=fake_pipeline,
        atr=None,
    )
    monkeypatch.setattr(routes, "scan_symbol", lambda symbol, timeframe="1h", **k: fake_row)
    monkeypatch.setattr(decisions_routes, "scan_symbol", lambda symbol, timeframe="1h", **k: fake_row)
    monkeypatch.setattr(paper_routes, "scan_symbol", lambda symbol, timeframe="1h", **k: fake_row)
    monkeypatch.setattr(paper_orders_routes, "scan_symbol", lambda symbol, timeframe="1h", **k: fake_row)

    resp = client.post(
        "/api/engine/paper/positions",
        params={"symbol": "ETHUSDT", "user_id": "test-user-no-atr"},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "no_atr_stop" in detail
    assert "WATCH" not in detail


def test_open_paper_position_404s_on_insufficient_history(monkeypatch):
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: [])
    resp = client.post(
        "/api/engine/paper/positions", params={"symbol": "BTCUSDT", "user_id": "test-user-routes"}
    )
    assert resp.status_code == 404


@requires_db
def test_close_paper_position_404s_for_an_unknown_id():
    resp = client.post("/api/engine/paper/positions/does-not-exist/close")
    assert resp.status_code == 404


def test_decisions_batch_returns_one_result_per_item_in_request_order(monkeypatch):
    # Optional batch endpoint (docs/HANDOFF-CURSOR-SESSION-2026-09-16-SOIR.md
    # §3) for the server's Journal watch job to fetch many confirmed symbols
    # concurrently instead of one HTTP call at a time. Fake scan_symbol per
    # (symbol, timeframe) -- order in the response must match the request,
    # not completion order, since results are collected via ThreadPoolExecutor.
    from app.agents.types import Direction, StrategyAgentOutput
    from app.decision.combiner import DecisionResult
    from app.decision.pipeline import PipelineResult
    from app.screener.service import ScreenerRow

    def fake_scan_symbol(symbol, timeframe="1h", **kwargs):
        if symbol == "MISSING":
            raise ValueError("not enough candles returned for MISSING 1h")
        decision = "BUY" if symbol == "BTCUSDT" else "SELL"
        direction = Direction.LONG if decision == "BUY" else Direction.SHORT
        agent_output = StrategyAgentOutput(
            agent="fake", direction=direction, probability=0.6, confidence=0.6, expected_value=0.1,
        )
        decision_result = DecisionResult(
            strategy_version="test", decision=decision, direction=direction,
            probability=0.6, confidence=0.6, agreement=1.0,
        )
        candle = Candle(time=1_700_000_000_000, open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0)
        return ScreenerRow(
            symbol=symbol, exchange="binance", timeframe=timeframe, price=1.0,
            candles=[candle], ichimoku=agent_output, rvol=agent_output, decision=decision_result,
            pipeline=PipelineResult(decision=decision, direction=direction, stages=[]),
        )

    monkeypatch.setattr(routes, "scan_symbol", fake_scan_symbol)


    monkeypatch.setattr(decisions_routes, "scan_symbol", fake_scan_symbol)


    monkeypatch.setattr(paper_routes, "scan_symbol", fake_scan_symbol)
    monkeypatch.setattr(paper_orders_routes, "scan_symbol", fake_scan_symbol)

    resp = client.post(
        "/api/engine/decisions/batch",
        json={
            "persist": False,
            "items": [
                {"symbol": "BTCUSDT", "timeframe": "1h"},
                {"symbol": "MISSING", "timeframe": "1h"},
                {"symbol": "ethusdt", "timeframe": "4h"},
            ],
        },
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 3

    assert results[0]["ok"] is True
    assert results[0]["symbol"] == "BTCUSDT"
    assert results[0]["pipeline"]["decision"] == "BUY"

    assert results[1]["ok"] is False
    assert results[1]["symbol"] == "MISSING"
    assert "error" in results[1]

    assert results[2]["ok"] is True
    assert results[2]["symbol"] == "ETHUSDT"
    assert results[2]["timeframe"] == "4h"
    assert results[2]["pipeline"]["decision"] == "SELL"


def test_decisions_batch_empty_items_returns_empty_results():
    resp = client.post("/api/engine/decisions/batch", json={"items": []})
    assert resp.status_code == 200
    assert resp.json() == {"results": []}


def test_decisions_batch_rejects_too_many_items():
    items = [{"symbol": "BTCUSDT", "timeframe": "1h"}] * 61
    resp = client.post("/api/engine/decisions/batch", json={"items": items})
    assert resp.status_code == 422
    assert "batch_too_large" in resp.json()["detail"]


def test_correlations_endpoint_defaults_to_the_watchlist_and_forwards_to_the_engine(monkeypatch):
    from app.correlation.engine import CorrelationMatrix, SkippedSymbol

    captured: dict = {}

    def fake_compute(symbols, *, timeframe, limit, method):
        captured["symbols"] = symbols
        captured["timeframe"] = timeframe
        captured["method"] = method
        return CorrelationMatrix(
            timeframe=timeframe, method=method, symbols=["BTCUSDT", "ETHUSDT"],
            sample_size=100, matrix=[[1.0, 0.5], [0.5, 1.0]],
            skipped=[SkippedSymbol(symbol="GHOST", reason="no_data_or_not_wired")],
        )

    monkeypatch.setattr(routes, "compute_correlation_matrix", fake_compute)


    monkeypatch.setattr(market_routes, "compute_correlation_matrix", fake_compute)

    resp = client.get("/api/engine/correlations")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbols"] == ["BTCUSDT", "ETHUSDT"]
    assert body["matrix"] == [[1.0, 0.5], [0.5, 1.0]]
    assert body["skipped"] == [{"symbol": "GHOST", "reason": "no_data_or_not_wired"}]
    # No `symbols` query param -> falls back to the default watchlist (28
    # entries today: crypto + biquote-backed forex/métal/index/énergie).
    assert len(captured["symbols"]) > 20
    assert "BTCUSDT" in captured["symbols"]
    assert captured["method"] == "log_returns"


def test_correlations_endpoint_accepts_explicit_symbols_and_method(monkeypatch):
    from app.correlation.engine import CorrelationMatrix

    captured: dict = {}

    def fake_compute(symbols, *, timeframe, limit, method):
        captured["symbols"] = symbols
        captured["method"] = method
        return CorrelationMatrix(
            timeframe=timeframe, method=method, symbols=symbols, sample_size=50,
            matrix=[[1.0, 0.1], [0.1, 1.0]], skipped=[],
        )

    monkeypatch.setattr(routes, "compute_correlation_matrix", fake_compute)


    monkeypatch.setattr(market_routes, "compute_correlation_matrix", fake_compute)

    resp = client.get(
        "/api/engine/correlations",
        params={"symbols": "AAPL,TSLA", "method": "price", "timeframe": "4h"},
    )
    assert resp.status_code == 200
    assert captured["symbols"] == ["AAPL", "TSLA"]
    assert captured["method"] == "price"


def test_correlations_endpoint_rejects_too_many_symbols():
    symbols = ",".join(f"SYM{i}" for i in range(41))
    resp = client.get("/api/engine/correlations", params={"symbols": symbols})
    assert resp.status_code == 422
    assert "too_many_symbols" in resp.json()["detail"]


def test_screener_endpoint_bypasses_cache_when_thresholds_are_overridden(monkeypatch):
    import app.screener.cache as cache_module

    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)
    monkeypatch.setattr(cache_module, "persist_scan", lambda session, row: None)

    # Poison the shared cache with an empty, stale-looking entry: if the
    # override path incorrectly fell back to the cache, this would be what
    # comes back instead of a fresh scan.
    from app.screener.cache import CacheEntry

    cache_module.screener_cache._entry = CacheEntry(rows=[], computed_at=0.0, timeframe="1h")

    resp = client.get("/api/engine/screener", params={"rvol_low": 0.1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["cache_age_seconds"] == 0.0
    assert len(body["rows"]) > 0
