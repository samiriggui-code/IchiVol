"""Reconstruct APT position 061c22cd: what would stop/TP have done after entry?"""
import httpx
from research_lab.data import fetch_klines, ms

ENTRY_MS = ms(2026, 9, 18, 20, 38) + 49_000  # 20:38:49 UTC
ENTRY, STOP, TP = 0.728364, 0.7030782857142857, 0.7789354285714284
QTY = 1719.8949848412212
rows = fetch_klines("APTUSDT", "1m", ms(2026, 9, 18, 20, 38), ms(2026, 9, 21))
print("bars", len(rows))
first = {}
for r in rows:
    o, t = r[0], r[0]
    if o + 60_000 <= ENTRY_MS:  # bar entirely before entry
        continue
    hi, lo, op = float(r[2]), float(r[3]), float(r[1])
    same_bar_ambiguous = o < ENTRY_MS  # bar that contains the entry instant
    if "stop" not in first and lo <= STOP:
        first["stop"] = (o, lo, op, same_bar_ambiguous)
    if "tp" not in first and hi >= TP:
        first["tp"] = (o, hi, op, same_bar_ambiguous)
    if len(first) == 2:
        break
from datetime import datetime, timezone
f = lambda t: datetime.fromtimestamp(t / 1000, timezone.utc).isoformat()
for k, v in first.items():
    print(k, f(v[0]), "extreme", v[1], "bar_open", v[2], "bar_contains_entry", v[3])
print("last close", rows[-1][4], f(rows[-1][0]))
