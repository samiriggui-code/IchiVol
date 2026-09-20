"""Per-bar, closed-candle pipeline decisions for the research harness.

Same components as the live screener (app/screener/service.scan_symbol) and the
existing backtest (app/backtest/experiments.prepare_variants), but:
  * every bar passed in is FULLY CLOSED (data.py drops the forming bar);
  * the higher-timeframe direction comes from the last HTF bar that had fully
    closed before the primary bar OPENED (experiments._align_mtf_directions);
  * output at index i is a function of candles[0..i] only (verified by
    tests/research_lab/test_signals_causal.py).
Not reproduced: OI/funding context (never changes a stage status -- see
decision/pipeline._participation_stage) and the live forming-bar behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents import ichimoku_agent, rvol_agent
from app.agents.types import Direction
from app.backtest.experiments import _align_mtf_directions
from app.decision.pipeline import PipelineResult, StageId, StageStatus, build_pipeline
from app.indicators.adx import compute_adx
from app.indicators.atr import compute_atr
from app.indicators.cvd import compute_cvd
from app.indicators.donchian import compute_donchian
from app.indicators.ichimoku import Candle
from app.indicators.location import compute_location
from app.indicators.structure import compute_structure

TF_SECONDS = {"1h": 3600, "4h": 14400}


def to_candles(rows: list[list]) -> list[Candle]:
    return [
        Candle(
            time=int(r[0] // 1000), open=float(r[1]), high=float(r[2]), low=float(r[3]),
            close=float(r[4]), volume=float(r[5]), taker_buy_volume=float(r[9]),
        )
        for r in rows
    ]


@dataclass(frozen=True)
class BarSignal:
    time: int  # open time (s) of the bar whose CLOSE produced this decision
    decision: str  # BUY | SELL | WATCH | NO_TRADE
    direction: Direction
    stop_distance: float | None
    rvol: float | None
    failed: tuple[str, ...]  # every stage that FAILed (multi-label); empty for BUY/SELL
    fail_codes: tuple[tuple[str, str], ...]  # (stage, first reason code) for each FAILed stage
    primary: str  # first blocking cause in _final_decision precedence, or "signal"
    mtf_aligned: bool | None


def _failed_stages(p: PipelineResult) -> tuple[str, ...]:
    return tuple(s.id.value for s in p.stages if s.status == StageStatus.FAIL)


def _fail_codes(p: PipelineResult) -> tuple[tuple[str, str], ...]:
    return tuple((s.id.value, (s.codes[0] if s.codes else "")) for s in p.stages if s.status == StageStatus.FAIL)


def _primary(p: PipelineResult) -> str:
    st = {s.id: s.status for s in p.stages}
    if p.decision in ("BUY", "SELL"):
        return "signal"
    if st[StageId.REGIME] == StageStatus.FAIL:
        return "regime"
    if p.direction == Direction.NEUTRAL:
        return "ichimoku_neutral"
    for sid, name in ((StageId.STRUCTURE, "structure_mtf"), (StageId.PARTICIPATION, "rvol_low"), (StageId.LOCATION, "location")):
        if st[sid] == StageStatus.FAIL:
            return name
    return "other"


def compute_bar_signals(candles: list[Candle], htf_candles: list[Candle] | None) -> list[BarSignal]:
    ichi = ichimoku_agent.analyze(candles)
    rvol = rvol_agent.analyze(candles)
    struct = compute_structure(candles)
    atr = compute_atr(candles)
    loc = compute_location(candles, struct)
    cvd = compute_cvd(candles)
    adx = compute_adx(candles)
    don = compute_donchian(candles)
    if htf_candles and len(htf_candles) >= 2:
        htf_out = ichimoku_agent.analyze(htf_candles)
        mtf = _align_mtf_directions(candles, htf_candles, htf_out, TF_SECONDS["4h"])
    else:
        mtf = [None] * len(candles)

    out: list[BarSignal] = []
    for i, c in enumerate(candles):
        io = ichi[i]
        aligned = (
            mtf[i] == io.direction
            if mtf[i] is not None and mtf[i] != Direction.NEUTRAL and io.direction != Direction.NEUTRAL
            else None
        )
        p = build_pipeline(io, rvol[i], struct[i], atr[i], aligned, loc[i], cvd[i], None, adx[i], don[i])
        sd = getattr(atr[i], "suggested_stop_distance", None)
        rv = rvol[i].metadata.get("rvol")
        out.append(
            BarSignal(
                time=c.time, decision=p.decision, direction=p.direction,
                stop_distance=sd if isinstance(sd, (int, float)) and sd > 0 else None,
                rvol=rv if isinstance(rv, (int, float)) else None,
                failed=_failed_stages(p), fail_codes=_fail_codes(p), primary=_primary(p), mtf_aligned=aligned,
            )
        )
    return out
