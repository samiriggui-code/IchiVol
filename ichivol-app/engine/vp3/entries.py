"""B0–B7 entry decision series (long-only). Pure functions of closed candles."""

from __future__ import annotations

from app.agents import ichimoku_agent, rvol_agent
from app.agents.types import Direction
from app.backtest.experiments import _align_mtf_directions
from app.decision.pipeline import build_pipeline
from app.indicators.adx import compute_adx
from app.indicators.atr import VolatilityRegime, compute_atr
from app.indicators.cvd import compute_cvd
from app.indicators.donchian import compute_donchian
from app.indicators.ichimoku import Candle, IchimokuParams, compute_ichimoku
from app.indicators.location import compute_location
from app.indicators.rvol import RvolParams, compute_rvol
from app.indicators.structure import compute_structure

from vp3 import RVOL_MIN, RVOL_WINDOW, WARMUP_BARS

ICHI_PARAMS = IchimokuParams(tenkan=9, kijun=26, senkou_b=52, displacement=26)
RVOL_PARAMS = RvolParams(primary_window=RVOL_WINDOW, significant_threshold=RVOL_MIN)


def _bullish_tk_cross(ichi: list, i: int) -> bool:
    """§2.1.1 — tenkan[t-1] ≤ kijun[t-1] and tenkan[t] > kijun[t]."""
    if i < 1:
        return False
    cur, prev = ichi[i], ichi[i - 1]
    if cur.tenkan is None or cur.kijun is None or prev.tenkan is None or prev.kijun is None:
        return False
    return prev.tenkan <= prev.kijun and cur.tenkan > cur.kijun


def _above_displayed_cloud(ichi: list, candles: list[Candle], i: int) -> bool:
    """§2.1.2 — close[t] > max(SA_aff, SB_aff) displayed at t (computed ≤ t−26)."""
    st = ichi[i]
    if st.senkou_a is None or st.senkou_b is None:
        return False
    return candles[i].close > max(st.senkou_a, st.senkou_b)


def b1_trigger(ichi: list, candles: list[Candle], i: int) -> bool:
    """§2.1 event trigger (no chikou)."""
    return _bullish_tk_cross(ichi, i) and _above_displayed_cloud(ichi, candles, i)


def htf_cloud_direction(ichi_row, close: float) -> str:
    """§2.2 — long / short / neutral from close vs displayed HTF cloud."""
    if ichi_row.senkou_a is None or ichi_row.senkou_b is None:
        return "neutral"
    top = max(ichi_row.senkou_a, ichi_row.senkou_b)
    bot = min(ichi_row.senkou_a, ichi_row.senkou_b)
    if close > top:
        return "long"
    if close < bot:
        return "short"
    return "neutral"


def align_htf_directions(
    ltf: list[Candle],
    htf: list[Candle],
    htf_ichi: list,
    *,
    ltf_seconds: int,
    htf_seconds: int,
) -> list[str]:
    """For each LTF bar, direction of last fully closed HTF at decision time (bar close)."""
    out: list[str] = ["neutral"] * len(ltf)
    if not htf:
        return out
    j = 0
    for i, c in enumerate(ltf):
        decision_s = c.time + ltf_seconds
        while j + 1 < len(htf) and htf[j + 1].time + htf_seconds <= decision_s:
            j += 1
        if htf[j].time + htf_seconds <= decision_s:
            out[i] = htf_cloud_direction(htf_ichi[j], htf[j].close)
        else:
            out[i] = "neutral"
    return out


def entry_mask(
    strategy: str,
    candles: list[Candle],
    *,
    htf_candles: list[Candle] | None = None,
    ltf_seconds: int = 3600,
    htf_seconds: int = 14400,
) -> list[bool]:
    """Return per-bar BUY eligibility (True = emit BUY at this close)."""
    n = len(candles)
    mask = [False] * n
    if n == 0:
        return mask

    if strategy == "B0":
        # Eligible from warm-up onward; WF gate + one_entry_per_signal_run pick the first bar in-fold.
        for i in range(WARMUP_BARS, n):
            mask[i] = True
        return mask

    ichi = compute_ichimoku(candles, ICHI_PARAMS)
    rvol = compute_rvol(candles, RVOL_PARAMS) if strategy in ("B2", "B5", "B6") else None
    atr = compute_atr(candles)

    htf_dir: list[str] | None = None
    if strategy in ("B5", "B6") and htf_candles:
        htf_ichi = compute_ichimoku(htf_candles, ICHI_PARAMS)
        htf_dir = align_htf_directions(
            candles, htf_candles, htf_ichi, ltf_seconds=ltf_seconds, htf_seconds=htf_seconds
        )

    if strategy == "B7":
        # Live pipeline Option B — same stack as research_lab.signals.compute_bar_signals
        ichi_out = ichimoku_agent.analyze(candles)
        rvol_out = rvol_agent.analyze(candles)
        struct = compute_structure(candles)
        loc = compute_location(candles, struct)
        cvd = compute_cvd(candles)
        adx = compute_adx(candles)
        don = compute_donchian(candles)
        if htf_candles and len(htf_candles) >= 2:
            htf_out = ichimoku_agent.analyze(htf_candles)
            mtf = _align_mtf_directions(candles, htf_candles, htf_out, htf_seconds)
        else:
            mtf = [None] * n
        for i in range(n):
            io = ichi_out[i]
            aligned = (
                mtf[i] == io.direction
                if mtf[i] is not None and mtf[i] != Direction.NEUTRAL and io.direction != Direction.NEUTRAL
                else None
            )
            p = build_pipeline(
                io,
                rvol_out[i],
                struct[i],
                atr[i],
                aligned,
                loc[i],
                cvd[i],
                None,
                adx[i],
                don[i],
            )
            mask[i] = p.decision == "BUY"
        return mask

    for i in range(n):
        if i < WARMUP_BARS:
            continue
        if strategy == "B1":
            mask[i] = b1_trigger(ichi, candles, i)
            continue
        if strategy == "B2":
            assert rvol is not None
            rv = rvol[i].rvol20
            mask[i] = b1_trigger(ichi, candles, i) and rv is not None and rv >= RVOL_MIN
            continue
        if strategy == "B5":
            assert rvol is not None and htf_dir is not None
            rv = rvol[i].rvol20
            mask[i] = (
                b1_trigger(ichi, candles, i)
                and rv is not None
                and rv >= RVOL_MIN
                and htf_dir[i] != "short"
            )
            continue
        if strategy == "B6":
            assert rvol is not None and htf_dir is not None
            rv = rvol[i].rvol20
            regime = atr[i].regime
            ok_regime = regime not in (VolatilityRegime.DEAD, VolatilityRegime.EXTREME)
            mask[i] = (
                b1_trigger(ichi, candles, i)
                and rv is not None
                and rv >= RVOL_MIN
                and htf_dir[i] != "short"
                and ok_regime
            )
            continue
        raise ValueError(f"unsupported strategy: {strategy}")
    return mask


def decisions_from_mask(mask: list[bool]) -> list[str]:
    return ["BUY" if m else "WATCH" for m in mask]
