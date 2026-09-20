from datetime import datetime, timezone
from app.indicators.ichimoku import Candle

def td_to_candles(values):
    out = []
    for v in values:
        t = int(datetime.strptime(v["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
        out.append(Candle(time=t, open=float(v["open"]), high=float(v["high"]), low=float(v["low"]), close=float(v["close"]), volume=0.0, taker_buy_volume=None))
    return out
