"""Paper order intents — propose before act (never live).

Builds a sized virtual order from the same risk rules as PaperBroker
(`size_position`) so the UI can show qty / stop / TP before the user
confirms. Opening still goes through `open_user_confirmed`.

T13a — TradePlan fields (trigger, invalidation, stop, targets, expiration,
session, codes, versions) are **serialization only**. Defaults keep current
behavior; opening paths ignore these until T13b.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

from sqlalchemy.orm import Session

from app.paper import broker as paper_broker
from app.paper.portfolio import ensure_baseline_portfolio, get_portfolio_by_code
from app.paper.risk import size_position
from app.paper.strategy_profiles import BASELINE_PROFILE
from app.screener.service import ScreenerRow

INTENT_SCHEMA_VERSION = "order_intent_v1"


@dataclass(frozen=True)
class OrderIntent:
    """Suggested paper trade — not an order until confirmed."""

    actionable: bool
    reason: str
    symbol: str
    timeframe: str
    pipeline_decision: str
    direction: str | None
    price: float
    stop_distance: float | None
    qty: float | None
    notional: float | None
    entry_fill: float | None
    stop_price: float | None
    take_profit_price: float | None
    risk_pct: float | None
    risk_amount: float | None
    portfolio_code: str
    equity: float | None
    cash: float | None
    volume_type: str | None = None
    evidence_summary: dict[str, Any] | None = None
    signal_timing: dict[str, Any] | None = None
    # —— T13a TradePlan (additive, serialization only) ——
    trigger: dict[str, Any] | None = None
    invalidation: list[str] | None = None
    stop: dict[str, Any] | None = None
    targets: list[dict[str, Any]] | None = None
    expiration: dict[str, Any] | None = None
    session: dict[str, Any] | None = None
    codes: list[str] | None = None
    versions: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OrderIntent:
        """Rebuild from JSON; missing T13a keys → None (backward compatible)."""
        known = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {}
        for name in known:
            if name in data:
                kwargs[name] = data[name]
        # Required legacy fields must be present for a valid intent payload.
        required = (
            "actionable",
            "reason",
            "symbol",
            "timeframe",
            "pipeline_decision",
            "direction",
            "price",
            "stop_distance",
            "qty",
            "notional",
            "entry_fill",
            "stop_price",
            "take_profit_price",
            "risk_pct",
            "risk_amount",
            "portfolio_code",
            "equity",
            "cash",
        )
        for key in required:
            if key not in kwargs:
                raise ValueError(f"OrderIntent.from_dict missing required key: {key}")
        return cls(**kwargs)


def _direction_for(decision: str) -> str | None:
    if decision == "BUY":
        return "LONG"
    if decision == "SELL":
        return "SHORT"
    return None


def _evidence_summary(row: ScreenerRow) -> dict[str, Any] | None:
    if row.evidence is None:
        return None
    h = row.evidence.historical
    return {
        "sample_size": h.sample_size,
        "sample_quality": h.sample_quality.value,
        "status": h.status,
        "calibration_note": row.evidence.calibration_note(),
    }


def _pipeline_codes(row: ScreenerRow) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for stage in getattr(row.pipeline, "stages", ()) or ():
        for code in getattr(stage, "codes", ()) or ():
            if code and code not in seen:
                seen.add(code)
                out.append(str(code))
    return out


def _invalidation_list(row: ScreenerRow) -> list[str]:
    decision = getattr(row, "decision", None)
    inv = getattr(decision, "invalidation", None) if decision is not None else None
    if not inv:
        return []
    return [str(x) for x in inv]


def _strategy_version(row: ScreenerRow) -> str:
    for src in (getattr(row, "pipeline", None), getattr(row, "decision", None)):
        if src is None:
            continue
        ver = getattr(src, "strategy_version", None)
        if ver:
            return str(ver)
    return "unknown"


def _session_stub(row: ScreenerRow) -> dict[str, Any]:
    """T13a stub — no calendar gate. Crypto = 24×7; else generic."""
    # ScreenerRow may not carry asset_class; infer from exchange heuristic.
    exchange = (getattr(row, "exchange", None) or "").lower()
    if exchange in ("binance", "binance_futures", "bybit"):
        return {"id": "crypto_24x7", "class": "crypto"}
    return {"id": "unspecified", "class": "unknown"}


def _expiration_from_timing(timing: dict[str, Any] | None) -> dict[str, Any] | None:
    if not timing:
        return None
    return {
        "signal_bar_close": timing.get("signal_bar_close"),
        "computed_at": timing.get("computed_at"),
        "stale": bool(timing.get("stale", False)),
        "lag_bars": timing.get("lag_bars"),
        "max_lag_bars": timing.get("max_lag_bars", 2),
    }


def _tradeplan_fields(
    *,
    row: ScreenerRow,
    direction: str | None,
    reason: str,
    stop_distance: float | None,
    stop_price: float | None,
    take_profit_price: float | None,
    take_profit_r: float | None,
    portfolio_code: str,
    signal_timing: dict[str, Any] | None,
) -> dict[str, Any]:
    codes = _pipeline_codes(row)
    if reason and reason != "ok" and reason not in codes:
        codes = [*codes, reason]

    stop_obj: dict[str, Any] | None = None
    if stop_price is not None or stop_distance is not None:
        stop_obj = {
            "price": stop_price,
            "distance": stop_distance,
            "source": "atr",
        }

    targets: list[dict[str, Any]] | None = None
    if take_profit_price is not None:
        targets = [
            {
                "price": take_profit_price,
                "r_multiple": take_profit_r,
                "fraction": 1.0,
            }
        ]

    return {
        "trigger": {
            "kind": "market",
            "pipeline_decision": row.pipeline.decision,
            "direction": direction,
        },
        "invalidation": _invalidation_list(row),
        "stop": stop_obj,
        "targets": targets,
        "expiration": _expiration_from_timing(signal_timing),
        "session": _session_stub(row),
        "codes": codes,
        "versions": {
            "strategy": _strategy_version(row),
            "intent": INTENT_SCHEMA_VERSION,
            "portfolio": portfolio_code,
        },
    }


def propose_order_intent(
    session: Session,
    row: ScreenerRow,
    *,
    portfolio_code: str = "ICHIVOL_BASELINE_V1",
) -> OrderIntent:
    """Dry-run sizing against the baseline (or named) paper portfolio."""
    direction = _direction_for(row.pipeline.decision)
    stop = row.atr.suggested_stop_distance if row.atr is not None else None
    volume_type = row.candles[-1].volume_type.value if row.candles else None
    evidence_summary = _evidence_summary(row)
    signal_timing = getattr(row, "signal_timing", None)

    def _blocked(reason: str, **extra: Any) -> OrderIntent:
        tp = _tradeplan_fields(
            row=row,
            direction=direction,
            reason=reason,
            stop_distance=stop,
            stop_price=None,
            take_profit_price=None,
            take_profit_r=None,
            portfolio_code=portfolio_code,
            signal_timing=signal_timing,
        )
        return OrderIntent(
            actionable=False,
            reason=reason,
            symbol=row.symbol,
            timeframe=row.timeframe,
            pipeline_decision=row.pipeline.decision,
            direction=direction,
            price=row.price,
            stop_distance=stop,
            qty=None,
            notional=None,
            entry_fill=None,
            stop_price=None,
            take_profit_price=None,
            risk_pct=extra.get("risk_pct"),
            risk_amount=None,
            portfolio_code=portfolio_code,
            equity=extra.get("equity"),
            cash=extra.get("cash"),
            volume_type=volume_type,
            evidence_summary=evidence_summary,
            signal_timing=signal_timing,
            **tp,
        )

    if (signal_timing or {}).get("stale"):
        return _blocked("stale_data")
    if direction is None:
        return _blocked("not_actionable")
    if stop is None or stop <= 0:
        return _blocked("no_stop")

    portfolio = ensure_baseline_portfolio(session)
    if portfolio_code != portfolio.code:
        alt = get_portfolio_by_code(session, portfolio_code)
        if alt is not None:
            portfolio = alt
            portfolio_code = portfolio.code

    profile = portfolio.strategy_profile or dict(BASELINE_PROFILE)
    equity = paper_broker.estimate_equity(session, portfolio)
    risk_pct = float(profile.get("risk_pct", 0.01))
    take_profit_r = float(profile.get("take_profit_r", 2.0))
    sized = size_position(
        equity=equity,
        cash=portfolio.cash,
        direction=direction,
        entry_price=row.price,
        stop_distance=stop,
        risk_pct=risk_pct,
        take_profit_r=take_profit_r,
        max_notional_pct=float(profile.get("max_notional_pct", 0.25)),
        commission_bps=float(profile.get("commission_bps", 5.0)),
        spread_bps=float(profile.get("spread_bps", 2.0)),
        slippage_bps=float(profile.get("slippage_bps", 3.0)),
    )
    if sized is None:
        return _blocked(
            "insufficient_cash_or_risk",
            risk_pct=risk_pct,
            equity=equity,
            cash=portfolio.cash,
        )

    tp = _tradeplan_fields(
        row=row,
        direction=direction,
        reason="ok",
        stop_distance=stop,
        stop_price=sized.stop_price,
        take_profit_price=sized.take_profit_price,
        take_profit_r=take_profit_r,
        portfolio_code=portfolio_code,
        signal_timing=signal_timing,
    )
    return OrderIntent(
        actionable=True,
        reason="ok",
        symbol=row.symbol,
        timeframe=row.timeframe,
        pipeline_decision=row.pipeline.decision,
        direction=direction,
        price=row.price,
        stop_distance=stop,
        qty=sized.qty,
        notional=sized.notional,
        entry_fill=sized.entry_fill,
        stop_price=sized.stop_price,
        take_profit_price=sized.take_profit_price,
        risk_pct=sized.risk_pct,
        risk_amount=sized.risk_amount,
        portfolio_code=portfolio_code,
        equity=equity,
        cash=portfolio.cash,
        volume_type=volume_type,
        evidence_summary=evidence_summary,
        signal_timing=signal_timing,
        **tp,
    )
