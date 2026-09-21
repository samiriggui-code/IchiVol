from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import OperationalError

from app.db.models import PaperOrder, PaperPortfolio, PaperPosition
from app.db.session import SessionLocal, engine
from app.paper.costs import compute_costs

try:
    with engine.connect():
        pass
    OK = True
except OperationalError:
    OK = False
pytestmark = pytest.mark.skipif(not OK, reason="dev Postgres not reachable")
CODE = "COSTSTEST"


@pytest.fixture
def s():
    sess = SessionLocal()
    sess.rollback()
    yield sess
    sess.rollback()
    sess.close()


def test_costs_identity_gross_equals_net_plus_commissions_plus_friction(s):
    now = datetime.now(timezone.utc)
    pf = PaperPortfolio(code=CODE, label=CODE, currency="EUR", valuation_mode="X", initial_cash=5000.0, cash=4000.0,
                        realized_pnl=0.0, strategy_profile={}, is_active=True, started_at=now, created_at=now, updated_at=now)
    s.add(pf); s.flush()
    s.add(PaperPosition(portfolio_id=pf.id, symbol="BTCUSDT", timeframe="1h", source="auto_watchlist", direction="LONG",
                        status="CLOSED", entry_time=now, entry_price=100.05, entry_decision="BUY", qty=10.0, notional=1000.5,
                        realized_pnl=-3.0))
    s.add(PaperOrder(portfolio_id=pf.id, symbol="BTCUSDT", timeframe="1h", side="BUY", requested_price=100.0, filled_price=100.05,
                     qty=10.0, notional=1000.5, fee=0.75, status="FILLED"))
    s.add(PaperOrder(portfolio_id=pf.id, symbol="XAUUSD", timeframe="1h", side="BUY", requested_price=50.0, filled_price=50.01,
                     qty=2.0, notional=100.0, fee=0.0, status="FILLED"))
    s.flush()
    c = compute_costs(s, pf, equity=4990.0)
    assert c["commissions"] == pytest.approx(0.75)
    assert c["spread_slippage"] == pytest.approx(10 * 0.05 + 2 * 0.01)
    assert c["net_result"] == pytest.approx(-10.0)
    assert c["gross_result"] == pytest.approx(-10.0 + 0.75 + 0.52)
    assert c["by_market"]["crypto"]["commissions"] == pytest.approx(0.75)
    assert c["by_market"]["autres marchés"]["total_costs"] == pytest.approx(0.02)
    assert c["closed_trades"] == 1 and c["losses"] == 1 and c["sum_losses"] == pytest.approx(-3.0)
