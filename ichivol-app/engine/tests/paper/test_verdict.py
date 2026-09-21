from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import OperationalError

from app.db.models import PaperPortfolio, PaperPosition
from app.db.session import SessionLocal, engine
from app.paper.verdict import compute_progress

try:
    with engine.connect():
        pass
    OK = True
except OperationalError:
    OK = False
pytestmark = pytest.mark.skipif(not OK, reason="dev Postgres not reachable")


def test_small_sample_is_never_a_verdict_and_top3_is_removed():
    s = SessionLocal()
    s.rollback()
    now = datetime.now(timezone.utc)
    pf = PaperPortfolio(code="VERDICTTEST", label="v", currency="EUR", valuation_mode="X", initial_cash=5000.0, cash=5000.0,
                        realized_pnl=0.0, strategy_profile={}, is_active=True, started_at=now - timedelta(days=10),
                        created_at=now, updated_at=now)
    s.add(pf); s.flush()
    for i, pnl in enumerate([50.0, 20.0, 10.0, -5.0, -6.0, -4.0]):
        s.add(PaperPosition(portfolio_id=pf.id, symbol=f"S{i}", timeframe="1h", source="auto_watchlist", direction="LONG",
                            status="CLOSED", entry_time=now - timedelta(days=9 - i), exit_time=now - timedelta(days=9 - i, hours=-1),
                            entry_price=1.0, entry_decision="BUY", qty=1.0, notional=1.0, realized_pnl=pnl))
    s.flush()
    try:
        p = compute_progress(s, pf, equity=5065.0, now=now)
        assert p["verdict"] == "insufficient" and p["closed_trades"] == 6
        assert p["net_without_top3"] == pytest.approx(-15.0) and p["top3_gains"] == pytest.approx(80.0)
        assert len(p["sub_period_net"]) == 3 and p["eta_days_to_min_trades"] > 0
    finally:
        s.rollback()
        s.close()
