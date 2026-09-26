"""Génère src/lib/chartIntelligenceMock.data.ts (MOCK Chart Intelligence).

Série OHLCV 1H synthétique déterministe + Ichimoku 9/26/52 (déplacement 26)
calculés ICI (hors React). Usage : python scripts/gen-chart-intelligence-mock.py
Les objets (Fib, FVG, BOS…) de chartIntelligenceMock.ts sont calés sur cette série.
"""
import pathlib
import json, math, random

random.seed(7)
T0 = 1788220800  # 2026-09-01 00:00 UTC
H = 3600
N = 111  # bars 0..110 (110 = current bar)

# (bar, price, kind) kind: H = swing high (exact high), L = swing low (exact low)
WP = [
    (0, 131.5, None), (12, 133.20, 'H'), (26, 127.80, 'L'), (32, 129.30, 'H'),
    (40, 124.30, 'L'), (50, 129.90, 'H'), (60, 127.60, 'L'), (72, 133.00, 'H'),
    (84, 129.40, 'L'), (92, 137.80, 'H'), (96, 134.90, 'L'), (99, 136.35, 'H'),
    (103, 134.70, None), (109, 132.30, None), (110, 131.38, None),
]

def path(i):
    for (b0, p0, _), (b1, p1, _) in zip(WP, WP[1:]):
        if b0 <= i <= b1:
            t = (i - b0) / (b1 - b0)
            t = 0.5 - 0.5 * math.cos(math.pi * t)
            return p0 + (p1 - p0) * t
    return WP[-1][1]

closes = [path(i) + (random.random() - 0.5) * 0.35 for i in range(N)]
wp = {b: (p, k) for b, p, k in WP}
for b, (p, k) in wp.items():
    if k == 'H':
        closes[b] = p - 0.25
    elif k == 'L':
        closes[b] = p + 0.25
closes[110] = 131.38

c = []
for i in range(N):
    o = closes[i - 1] if i else closes[0] + 0.2
    cl = closes[i]
    hi = max(o, cl) + random.uniform(0.08, 0.35)
    lo = min(o, cl) - random.uniform(0.08, 0.35)
    c.append([o, hi, lo, cl])

def set_bar(i, o=None, h=None, l=None, cl=None):
    b = c[i]
    if o is not None: b[0] = o
    if cl is not None: b[3] = cl
    if h is not None: b[1] = h
    if l is not None: b[2] = l
    b[1] = max(b[1], b[0], b[3]); b[2] = min(b[2], b[0], b[3])

# Enforce exact swing extremes and keep neighbours strictly inside.
for b, (p, k) in wp.items():
    if k == 'H':
        c[b][1] = p
        for j in range(max(0, b - 4), min(N, b + 5)):
            if j != b and c[j][1] >= p:
                c[j][1] = p - random.uniform(0.15, 0.5)
                c[j][0] = min(c[j][0], c[j][1]); c[j][3] = min(c[j][3], c[j][1])
    elif k == 'L':
        c[b][2] = p
        for j in range(max(0, b - 4), min(N, b + 5)):
            if j != b and c[j][2] <= p:
                c[j][2] = p + random.uniform(0.15, 0.5)
                c[j][0] = max(c[j][0], c[j][2]); c[j][3] = max(c[j][3], c[j][2])

# Old bullish FVG 130.00 -> 130.40 (bars 64-66), filled by bar 84 low 129.40.
set_bar(64, o=129.55, cl=129.90, h=130.00, l=129.45)
set_bar(65, o=129.90, cl=130.85, h=131.00, l=129.85)
set_bar(66, o=130.85, cl=131.20, h=131.45, l=130.40)
# Active bullish FVG 131.20 -> 131.85 (bars 86-88).
set_bar(86, o=130.70, cl=131.05, h=131.20, l=130.55)
set_bar(87, o=131.05, cl=132.40, h=132.55, l=130.95)
set_bar(88, o=132.40, cl=133.30, h=133.45, l=131.85)
set_bar(89, o=133.30, cl=134.20, h=134.35, l=132.90)
# Bearish FVG 134.60 -> 135.10 (bars 100-102), later partially filled (bar 103-104 high 134.85).
set_bar(100, o=136.10, cl=135.40, h=136.15, l=135.10)
set_bar(101, o=135.40, cl=134.30, h=135.45, l=134.20)
set_bar(102, o=134.30, cl=134.10, h=134.60, l=133.95)
set_bar(103, o=134.10, cl=134.60, h=134.85, l=134.00)
set_bar(104, o=134.60, cl=134.00, h=134.70, l=133.80)
for i in range(105, 110):
    c[i][1] = min(c[i][1], 134.55)
    c[i][0] = min(c[i][0], c[i][1]); c[i][3] = min(c[i][3], c[i][1])
for i in range(89, 110):
    if c[i][2] < 131.95:
        c[i][2] = 131.95 + random.uniform(0.02, 0.2)
        c[i][0] = max(c[i][0], c[i][2]); c[i][3] = max(c[i][3], c[i][2])
# Current bar sits inside the confluence zone.
set_bar(110, o=132.25, cl=131.38, h=132.40, l=131.30)
for i in range(1, N):
    pass

for i in range(N):
    o,h,l,cl=c[i]
    lo,hi=min(l,h),max(l,h)
    if hi-lo<0.05: lo-=0.05
    c[i]=[min(max(o,lo),hi),hi,lo,min(max(cl,lo),hi)]
for i in range(N):
    o,h,l,cl=c[i]; assert l<=min(o,cl)<=max(o,cl)<=h, (i,c[i])
vol = []
for i in range(N):
    base = 1800 + random.uniform(-300, 300)
    body = abs(c[i][3] - c[i][0])
    v = base * (1 + body * 0.9)
    if 85 <= i <= 92: v *= 1.6
    if 46 <= i <= 50 or 61 <= i <= 66: v *= 1.3
    vol.append(v)
vol[110] = sum(vol[90:110]) / 20 * 1.42

candles = [
    {"time": T0 + i * H, "open": round(o, 2), "high": round(h, 2), "low": round(l, 2),
     "close": round(cl, 2), "volume": round(vol[i], 1)}
    for i, (o, h, l, cl) in enumerate(c)
]

def mid(i, n):
    if i < n - 1: return None
    hs = [x["high"] for x in candles[i - n + 1:i + 1]]
    ls = [x["low"] for x in candles[i - n + 1:i + 1]]
    return (max(hs) + min(ls)) / 2

ichi = []
for i in range(N):
    t, k = mid(i, 9), mid(i, 26)
    ichi.append({"time": candles[i]["time"], "tenkan": None if t is None else round(t, 3),
                 "kijun": None if k is None else round(k, 3)})
proj = []
for i in range(N):
    t, k, b = mid(i, 9), mid(i, 26), mid(i, 52)
    if t is None or k is None or b is None: continue
    proj.append({"time": T0 + (i + 25) * H, "senkouA": round((t + k) / 2, 3), "senkouB": round(b, 3)})


TEMPLATE = "/**\n * MOCK — série OHLCV 1H synthétique + Ichimoku (9/26/52, déplacement 26)\n * pré-calculés HORS React (script Python de génération, cf. INTEGRATION.md).\n * Représente ce que l'engine renverra ; React ne recalcule rien.\n * Fichier généré — ne pas éditer à la main.\n */\n\nimport type {{ ProjectedKumoPoint }} from './engineIndicators'\nimport type {{ IntelligenceIchimokuPoint }} from './chartIntelligence'\nimport type {{ Candle }} from './types'\n\n/** 2026-09-01 00:00 UTC */\nexport const MOCK_T0 = {T0}\nexport const MOCK_BAR_SECONDS = 3600\n\n/** [open, high, low, close, volume] */\nconst OHLCV: ReadonlyArray<readonly [number, number, number, number, number]> = [\n{rows},\n]\n\n/** [tenkan, kijun] alignés sur OHLCV */\nconst ICHI: ReadonlyArray<readonly [number | null, number | null]> = [\n{ich},\n]\n\n/** [barIndex projeté (+25), senkouA, senkouB] */\nconst KUMO: ReadonlyArray<readonly [number, number, number]> = [\n{pj},\n]\n\nexport const MOCK_CANDLES: Candle[] = OHLCV.map(([open, high, low, close, volume], i) => ({{\n  time: MOCK_T0 + i * MOCK_BAR_SECONDS,\n  open,\n  high,\n  low,\n  close,\n  volume,\n}}))\n\nexport const MOCK_ICHIMOKU: IntelligenceIchimokuPoint[] = ICHI.map(([tenkan, kijun], i) => ({{\n  time: MOCK_T0 + i * MOCK_BAR_SECONDS,\n  tenkan,\n  kijun,\n}}))\n\nexport const MOCK_PROJECTION: ProjectedKumoPoint[] = KUMO.map(([bar, senkouA, senkouB]) => ({{\n  time: MOCK_T0 + bar * MOCK_BAR_SECONDS,\n  senkouA,\n  senkouB,\n}}))\n"

T0c = candles[0]["time"]
rows = ",\n".join(f"  [{x['open']}, {x['high']}, {x['low']}, {x['close']}, {x['volume']}]" for x in candles)
nz = lambda v: "null" if v is None else v
ich_rows = ",\n".join(f"  [{nz(p['tenkan'])}, {nz(p['kijun'])}]" for p in ichi)
pj_rows = ",\n".join(f"  [{(p['time'] - T0c) // H}, {p['senkouA']}, {p['senkouB']}]" for p in proj)
OUT = pathlib.Path(__file__).resolve().parent.parent / "src" / "lib" / "chartIntelligenceMock.data.ts"
OUT.write_text(TEMPLATE.format(T0=T0c, rows=rows, ich=ich_rows, pj=pj_rows))
print("written", OUT)
