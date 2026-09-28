"""Live pipeline decisions per closed 1h bar, and the C1 concordance check against the live window.

Decisions come from ``research_lab.signals.compute_bar_signals`` (the same ``build_pipeline`` stack as
``app/screener/service.scan_symbol``), computed once over the whole series. The live screener only sees the last
299 closed bars: C1 measures, on a pre-registered random sample, whether that changes the decision.

Eligibility: a symbol can only trade from its 299th closed 1h bar (the live fetch never has fewer bars for
these symbols). Earlier bars are fed to the simulator as ``WARMUP`` (never BUY).
"""

from __future__ import annotations

import hashlib
import pickle
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

from app.agents.types import Direction
from app.indicators.ichimoku import Candle
from research_lab.replica import live_like_signal
from research_lab.signals import BarSignal, compute_bar_signals

from vpp import LIVE_WINDOW_BARS, SEED
from vpp.data import data_root, load_candles

HTF_SECONDS = 14_400
LTF_SECONDS = 3_600


def _cache_path(symbol: str, digests: tuple[str, str], root: Path) -> Path:
    key = hashlib.sha256(("|".join(digests) + "|v1").encode()).hexdigest()[:16]
    return root / "signals" / f"{symbol}_1h_{key}.pkl"


def _compute(symbol: str, root: Path | None = None) -> tuple[str, list[BarSignal]]:
    root = data_root(root)
    c1, d1 = load_candles(symbol, "1h", root)
    c4, d4 = load_candles(symbol, "4h", root)
    path = _cache_path(symbol, (d1, d4), root)
    if path.exists():
        return symbol, pickle.loads(path.read_bytes())
    sigs = compute_bar_signals(c1, c4)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(sigs))
    return symbol, sigs


def compute_all(symbols: list[str], root: Path | None = None, workers: int = 4) -> dict[str, list[BarSignal]]:
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return dict(ex.map(_compute, symbols, [root] * len(symbols)))


def warmup_signal(sig: BarSignal) -> BarSignal:
    return replace(sig, decision="WARMUP", direction=Direction.NEUTRAL, primary="warmup")


def build_feed(candles: list[Candle], sigs: list[BarSignal]) -> dict[int, tuple[Candle, BarSignal]]:
    if len(candles) != len(sigs):
        raise ValueError("candles / signals length mismatch")
    feed: dict[int, tuple[Candle, BarSignal]] = {}
    for i, (c, s) in enumerate(zip(candles, sigs)):
        if s.time != c.time:
            raise ValueError(f"signal/candle time mismatch at {i}")
        feed[c.time] = (c, s if i >= LIVE_WINDOW_BARS - 1 else warmup_signal(s))
    return feed


# --- C1 concordance ----------------------------------------------------------------------------------------------

@lru_cache(maxsize=4)
def _series(symbol: str, root: str | None) -> tuple[list[Candle], list[Candle]]:
    r = Path(root) if root else None
    return load_candles(symbol, "1h", r)[0], load_candles(symbol, "4h", r)[0]


def _live_decision(args: tuple[str, int, str | None]) -> tuple[str, int, str]:
    symbol, i, root = args
    c1, c4 = _series(symbol, root)
    decision_s = c1[i].time + LTF_SECONDS
    window = c1[max(0, i - (LIVE_WINDOW_BARS - 1)): i + 1]
    htf = [h for h in c4 if h.time + HTF_SECONDS <= decision_s][-LIVE_WINDOW_BARS:]
    return symbol, i, live_like_signal(window, htf).decision


def concordance_sample(
    candles: dict[str, list[Candle]], window: tuple[int, int], n: int = 300, seed: int = SEED,
) -> list[tuple[str, int]]:
    """Uniform draw of (symbol, bar index) among eligible bars whose open time is inside ``window``."""
    pool = [
        (s, i)
        for s in sorted(candles)
        for i, c in enumerate(candles[s])
        if i >= LIVE_WINDOW_BARS - 1 and window[0] <= c.time < window[1]
    ]
    return sorted(random.Random(seed).sample(pool, n))


def concordance(
    sample: list[tuple[str, int]], sigs: dict[str, list[BarSignal]], root: Path | None = None, workers: int = 4,
) -> dict:
    args = [(s, i, str(root) if root else None) for s, i in sample]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        live = list(ex.map(_live_decision, args, chunksize=15))  # sorted sample: chunks stay on one symbol
    rows = [(s, i, sigs[s][i].decision, d) for s, i, d in live]
    agree = sum(1 for _, _, full, lv in rows if full == lv)
    buy_full = sum(1 for r in rows if r[2] == "BUY")
    buy_live = sum(1 for r in rows if r[3] == "BUY")
    return {
        "n": len(rows),
        "agree": agree,
        "agree_rate": agree / len(rows) if rows else None,
        "buy_full_history": buy_full,
        "buy_live_window": buy_live,
        "disagreements": [
            {"symbol": s, "index": i, "full_history": f, "live_window": lv} for s, i, f, lv in rows if f != lv
        ],
    }
