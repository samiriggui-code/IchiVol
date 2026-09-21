from app.paper.broker import _commission, _commission_bps
from app.paper.strategy_profiles import BASELINE_CODE, profile_for


def test_commission_is_per_asset_class():
    p = profile_for(BASELINE_CODE)
    assert _commission_bps(p, "BTCUSDT") == 7.5  # spot crypto fee
    assert _commission_bps(p, "XAUUSD") == 0.0  # CFD: spread only
    assert _commission(p, 1000.0, 1.0, "BTCUSDT") == 0.75
    assert _commission(p, 1000.0, 1.0, "SPX") == 0.0
    assert _commission(p, 1000.0, 1.0) == 0.75  # unknown symbol falls back to the profile rate
