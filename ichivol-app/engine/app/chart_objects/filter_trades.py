"""T4b — structured post-backtest trade filters (explainability / Claude tools).

Does not re-run or alter fills — only subsets of already computed trade dicts.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

EXIT_REASONS = frozenset({"stop", "target", "signal", "eod", "max_hold"})
DIRECTIONS = frozenset({"LONG", "SHORT"})
# Orthogonal Lab regime tags (strategy_lab.regime.RegimeTags.labels)
REGIME_LABELS = frozenset(
    {
        "TRENDING",
        "RANGING",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "NORMAL_VOLATILITY",
        "BULL",
        "BEAR",
        "SIDEWAYS",
    }
)


def _norm_dir(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return str(value).strip().upper()


def _why_has_passed_key(why: Sequence[dict[str, Any]] | None, key: str) -> bool:
    if not why or not key:
        return False
    needle = key.strip()
    for leaf in why:
        if not isinstance(leaf, dict):
            continue
        if leaf.get("key") == needle and leaf.get("passed") is True:
            return True
    return False


def trade_matches_filters(
    trade: dict[str, Any],
    *,
    outcome: str | None = None,
    exit_reason: str | None = None,
    direction: str | None = None,
    why_entered_key: str | None = None,
    regime_label: str | None = None,
) -> bool:
    """AND of optional filters. ``outcome='all'`` or None = no outcome filter."""
    if outcome and outcome != "all" and trade.get("outcome") != outcome:
        return False
    if exit_reason and trade.get("exit_reason") != exit_reason:
        return False
    want_dir = _norm_dir(direction)
    if want_dir and _norm_dir(str(trade.get("direction") or "")) != want_dir:
        return False
    if why_entered_key:
        why = trade.get("why_entered")
        if not isinstance(why, list):
            why = []
        if not _why_has_passed_key(why, why_entered_key):
            return False
    if regime_label:
        labels = trade.get("regime_labels") or ()
        if not isinstance(labels, (list, tuple)):
            labels = ()
        if regime_label not in labels:
            return False
    return True


def filter_trades(
    trades: Iterable[dict[str, Any]],
    *,
    outcome: str | None = None,
    exit_reason: str | None = None,
    direction: str | None = None,
    why_entered_key: str | None = None,
    regime_label: str | None = None,
) -> list[dict[str, Any]]:
    return [
        t
        for t in trades
        if trade_matches_filters(
            t,
            outcome=outcome,
            exit_reason=exit_reason,
            direction=direction,
            why_entered_key=why_entered_key,
            regime_label=regime_label,
        )
    ]


def filter_rejected(
    rejected: Iterable[dict[str, Any]],
    *,
    direction: str | None = None,
    why_entered_key: str | None = None,
    regime_label: str | None = None,
) -> list[dict[str, Any]]:
    """Rejected signals have no outcome/exit_reason — direction / why / regime."""
    want_dir = _norm_dir(direction)
    out: list[dict[str, Any]] = []
    for r in rejected:
        if want_dir and _norm_dir(str(r.get("direction") or "")) != want_dir:
            continue
        if why_entered_key:
            why = r.get("why_entered")
            if not isinstance(why, list):
                why = []
            if not _why_has_passed_key(why, why_entered_key):
                continue
        if regime_label:
            labels = r.get("regime_labels") or ()
            if not isinstance(labels, (list, tuple)):
                labels = ()
            if regime_label not in labels:
                continue
        out.append(r)
    return out


def validate_filter_args(
    *,
    outcome: str | None = None,
    exit_reason: str | None = None,
    direction: str | None = None,
    regime_label: str | None = None,
) -> None:
    """Raise ValueError on unknown enum values."""
    if outcome is not None and outcome not in ("all", "win", "loss", "flat"):
        raise ValueError(f"invalid outcome filter: {outcome!r}")
    if exit_reason is not None and exit_reason not in EXIT_REASONS:
        raise ValueError(
            f"invalid exit_reason: {exit_reason!r} (expected one of {sorted(EXIT_REASONS)})"
        )
    if direction is not None and direction != "":
        d = _norm_dir(direction)
        if d not in DIRECTIONS:
            raise ValueError(f"invalid direction: {direction!r} (LONG|SHORT)")
    if regime_label is not None and regime_label != "":
        if regime_label not in REGIME_LABELS:
            raise ValueError(
                f"invalid regime_label: {regime_label!r} "
                f"(expected one of {sorted(REGIME_LABELS)})"
            )
