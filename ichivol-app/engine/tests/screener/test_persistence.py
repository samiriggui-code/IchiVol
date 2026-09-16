from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from app.db.models import Asset
from app.db.models import Candle as CandleRow
from app.db.models import AgentPrediction, Decision, StrategySignal
from app.db.session import SessionLocal, engine
from app.indicators.ichimoku import Candle
from app.market_data import binance, binance_futures
from app.screener.persistence import persist_scan
from app.screener.service import scan_symbol

try:
    with engine.connect():
        pass
    DB_AVAILABLE = True
except OperationalError:
    DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not DB_AVAILABLE, reason="ichivol_engine_dev Postgres not reachable")

SYMBOL = "PERSISTTEST"


@pytest.fixture(autouse=True)
def _no_live_oi_funding_calls(monkeypatch):
    # scan_symbol() also fetches OI/Funding for Binance-backed symbols
    # (app/indicators/oi_funding.py, V2) -- stub it so this stays a pure
    # DB-persistence test, not a network test.
    monkeypatch.setattr(binance_futures, "fetch_open_interest_hist", lambda *a, **k: [])
    monkeypatch.setattr(binance_futures, "fetch_funding_rate_hist", lambda *a, **k: [])


def _uptrend_with_spike(n: int) -> list[Candle]:
    volumes = [50.0] * (n - 1) + [250.0]
    return [
        Candle(time=i, open=100 + i, high=101 + i, low=99 + i, close=100.5 + i, volume=volumes[i])
        for i in range(n)
    ]


def _cleanup(session):
    asset = session.query(Asset).filter_by(symbol=SYMBOL, exchange="binance").one_or_none()
    if asset is None:
        return
    signal_ids = [s.id for s in session.query(StrategySignal).filter_by(symbol=SYMBOL).all()]
    if signal_ids:
        session.query(Decision).filter(Decision.signal_id.in_(signal_ids)).delete(
            synchronize_session=False
        )
        session.query(AgentPrediction).filter(
            AgentPrediction.signal_id.in_(signal_ids)
        ).delete(synchronize_session=False)
        session.query(StrategySignal).filter_by(symbol=SYMBOL).delete()
    session.query(CandleRow).filter_by(asset_id=asset.id).delete()
    session.delete(asset)
    session.commit()


def test_persist_scan_writes_full_traceable_chain(monkeypatch):
    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)
    row = scan_symbol(SYMBOL, timeframe="1h", limit=160)

    session = SessionLocal()
    try:
        _cleanup(session)
        decision_row = persist_scan(session, row)

        assert decision_row.decision == "STRONG_BUY"
        signal = session.get(StrategySignal, decision_row.signal_id)
        assert signal.symbol == SYMBOL
        assert signal.kind in ("brk_long", "tk_long", "state_scan")

        predictions = session.query(AgentPrediction).filter_by(signal_id=signal.id).all()
        assert {p.agent for p in predictions} == {"ICHIMOKU_AGENT", "RVOL_AGENT"}
    finally:
        _cleanup(session)
        session.close()
