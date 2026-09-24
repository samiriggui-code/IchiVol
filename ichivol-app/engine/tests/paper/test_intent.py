"""Tests for paper order intent (propose before act + T13a TradePlan)."""

from __future__ import annotations

from app.agents import ichimoku_agent, rvol_agent
from app.db.session import SessionLocal
from app.decision.combiner import combine_ichimoku_rvol
from app.decision.pipeline import build_pipeline
from app.indicators.atr import compute_atr
from app.indicators.ichimoku import Candle
from app.market_data.volume_semantics import VolumeType
from app.paper.intent import INTENT_SCHEMA_VERSION, OrderIntent, propose_order_intent
from app.paper.portfolio import ensure_baseline_portfolio
from app.screener.service import ScreenerRow

_LEGACY_KEYS = (
    "actionable",
    "reason",
    "symbol",
    "timeframe",
    "pipeline_decision",
    "direction",
    "price",
    "stop_distance",
    "qty",
    "notional",
    "entry_fill",
    "stop_price",
    "take_profit_price",
    "risk_pct",
    "risk_amount",
    "portfolio_code",
    "equity",
    "cash",
    "volume_type",
    "evidence_summary",
    "signal_timing",
)

_T13A_KEYS = (
    "trigger",
    "invalidation",
    "stop",
    "targets",
    "expiration",
    "session",
    "codes",
    "versions",
)


def _candles(n: int = 120) -> list[Candle]:
    out = []
    for i in range(n):
        px = 100 + i * 0.5
        v = 300.0 if i == n - 1 else 100.0
        out.append(
            Candle(
                time=1_700_000_000 + i * 3600,
                open=px,
                high=px + 1,
                low=px - 1,
                close=px + 0.4,
                volume=v,
                volume_type=VolumeType.EXCHANGE_VOLUME,
            )
        )
    return out


def _row(*, stale: bool = False) -> ScreenerRow:
    candles = _candles()
    ichi = ichimoku_agent.analyze(candles)[-1]
    rvol = rvol_agent.analyze(candles)[-1]
    decision = combine_ichimoku_rvol(ichi, rvol)
    pipeline = build_pipeline(ichimoku=ichi, rvol=rvol, atr=compute_atr(candles)[-1])
    timing = None
    if stale:
        timing = {
            "stale": True,
            "lag_bars": 5,
            "max_lag_bars": 2,
            "signal_bar_close": 1,
            "computed_at": 2,
        }
    return ScreenerRow(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        price=candles[-1].close,
        candles=candles,
        ichimoku=ichi,
        rvol=rvol,
        decision=decision,
        pipeline=pipeline,
        atr=compute_atr(candles)[-1],
        signal_timing=timing,
    )


def test_propose_intent_blocked_when_watch():
    row = _row()
    session = SessionLocal()
    try:
        ensure_baseline_portfolio(session)
        session.commit()
        intent = propose_order_intent(session, row)
        assert intent.symbol == "BTCUSDT"
        assert intent.to_dict()["reason"] in (
            "ok",
            "not_actionable",
            "no_stop",
            "insufficient_cash_or_risk",
        )
        if intent.actionable:
            assert intent.qty and intent.qty > 0
            assert intent.stop_price is not None
            assert intent.take_profit_price is not None
    finally:
        session.close()


def test_t13a_tradeplan_keys_always_present():
    row = _row()
    session = SessionLocal()
    try:
        ensure_baseline_portfolio(session)
        session.commit()
        intent = propose_order_intent(session, row)
        payload = intent.to_dict()
        for key in _LEGACY_KEYS:
            assert key in payload
        for key in _T13A_KEYS:
            assert key in payload
        assert payload["versions"]["intent"] == INTENT_SCHEMA_VERSION
        assert payload["versions"]["portfolio"] == intent.portfolio_code
        assert payload["trigger"]["kind"] == "market"
        assert payload["session"]["class"] == "crypto"
        assert isinstance(payload["invalidation"], list)
        assert isinstance(payload["codes"], list)
        if intent.actionable:
            assert payload["stop"]["price"] == intent.stop_price
            assert payload["targets"][0]["price"] == intent.take_profit_price
            assert payload["targets"][0]["fraction"] == 1.0
        else:
            assert intent.reason in payload["codes"] or intent.reason == "ok"
    finally:
        session.close()


def test_t13a_round_trip_from_dict():
    row = _row()
    session = SessionLocal()
    try:
        ensure_baseline_portfolio(session)
        session.commit()
        intent = propose_order_intent(session, row)
        rebuilt = OrderIntent.from_dict(intent.to_dict())
        assert rebuilt == intent
    finally:
        session.close()


def test_t13a_from_dict_legacy_without_tradeplan_keys():
    legacy = {
        "actionable": False,
        "reason": "not_actionable",
        "symbol": "ETHUSDT",
        "timeframe": "1h",
        "pipeline_decision": "WATCH",
        "direction": None,
        "price": 1.0,
        "stop_distance": None,
        "qty": None,
        "notional": None,
        "entry_fill": None,
        "stop_price": None,
        "take_profit_price": None,
        "risk_pct": None,
        "risk_amount": None,
        "portfolio_code": "ICHIVOL_BASELINE_V1",
        "equity": None,
        "cash": None,
    }
    intent = OrderIntent.from_dict(legacy)
    assert intent.trigger is None
    assert intent.codes is None
    assert intent.versions is None
    assert intent.reason == "not_actionable"


def test_t13a_stale_sets_expiration():
    row = _row(stale=True)
    session = SessionLocal()
    try:
        ensure_baseline_portfolio(session)
        session.commit()
        intent = propose_order_intent(session, row)
        assert intent.actionable is False
        assert intent.reason == "stale_data"
        assert intent.expiration is not None
        assert intent.expiration["stale"] is True
        assert "stale_data" in (intent.codes or [])
    finally:
        session.close()
