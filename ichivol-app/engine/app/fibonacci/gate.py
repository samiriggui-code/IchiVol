"""Optional Fibonacci confluence gate for experimental paper profiles.

Downgrade only. Baseline keeps ``fibonacci_filter`` None.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Sequence

from app.decision.pipeline import PipelineResult, StageId, StageStatus
from app.fibonacci.context import compute_fib_context
from app.indicators.ichimoku import Candle


@dataclass(frozen=True)
class FibonacciGateResult:
    pipeline: PipelineResult
    blocked: bool
    reason: str | None
    fibonacci_payload: dict[str, Any] | None
    raw_decision: str


def apply_fibonacci_gate(
    pipeline: PipelineResult,
    candles: Sequence[Candle],
    profile: dict[str, Any],
) -> FibonacciGateResult:
    """If profile has no fibonacci_filter, return pipeline unchanged."""
    raw = pipeline.decision
    filt = profile.get("fibonacci_filter")
    if not filt or raw not in ("BUY", "SELL"):
        return FibonacciGateResult(pipeline, False, None, None, raw)

    if not candles:
        return FibonacciGateResult(
            pipeline, False, "insufficient_candles", None, raw
        )

    atr_mult = float(profile.get("fibonacci_confluence_atr_mult", 0.5))
    require_key = bool(profile.get("fibonacci_require_key_level", True))
    require_align = bool(profile.get("fibonacci_require_impulse_align", True))
    ctx = compute_fib_context(candles, confluence_atr_mult=atr_mult)
    if ctx is None:
        return FibonacciGateResult(pipeline, False, "no_swings", None, raw)

    payload = ctx.to_payload()
    payload["filter"] = filt

    impulse_ok = (raw == "BUY" and ctx.impulse == "up") or (
        raw == "SELL" and ctx.impulse == "down"
    )
    payload["impulse_aligned"] = impulse_ok

    if filt != "require_confluence":
        return FibonacciGateResult(pipeline, False, None, payload, raw)

    reasons: list[str] = []
    ok = ctx.key_confluence if require_key else ctx.confluence
    if not ok:
        reasons.append("fib_no_confluence")
    if require_align and not impulse_ok:
        reasons.append("fib_impulse_misaligned")

    if not reasons:
        return FibonacciGateResult(pipeline, False, None, payload, raw)

    reason = ";".join(reasons)
    stages: list = []
    for stage in pipeline.stages:
        if stage.id == StageId.LOCATION:
            stages.append(
                replace(
                    stage,
                    status=StageStatus.FAIL,
                    summary=f"{stage.summary} · FIB block: {reason}",
                    codes=[*stage.codes, "fibonacci_block", *reasons],
                )
            )
        else:
            stages.append(stage)
    gated = PipelineResult(
        decision="NO_TRADE",
        direction=pipeline.direction,
        stages=stages,
        strategy_version=pipeline.strategy_version,
    )
    return FibonacciGateResult(gated, True, reason, payload, raw)
