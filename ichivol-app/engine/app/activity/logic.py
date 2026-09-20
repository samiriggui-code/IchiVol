"""Activity feed logic -- pure functions (no DB, no HTTP) so they are testable.

The engine already records what the automated circuit does (backtest
snapshots, the paper journal, shadow trades); nothing turned that into
something a human can read. These helpers cluster and summarize it.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta

# One collection cycle writes its ~200 rows over a few minutes; a longer gap
# means a different cycle (an engine restart, or the next daily run).
RUN_GAP = timedelta(minutes=15)

# Below this many trades per (symbol, timeframe) a profit factor / win rate is
# noise. The pipeline averages ~6 trades per 1000 bars: its PF must not be read
# as an edge.
MIN_TRADES_PER_PAIR = 30

PIPELINE = "PIPELINE"
ICHIMOKU_ONLY = "ICHIMOKU_ONLY"


@dataclass(frozen=True)
class SnapshotLite:
    computed_at: datetime
    symbol: str
    timeframe: str
    experiment: str
    num_trades: int
    sharpe: float | None
    profit_factor: float | None
    expectancy: float | None
    win_rate: float | None


def cluster_runs(rows: list[SnapshotLite]) -> list[list[SnapshotLite]]:
    """Group snapshot rows into collection runs, oldest first."""
    ordered = sorted(rows, key=lambda r: r.computed_at)
    runs: list[list[SnapshotLite]] = []
    for row in ordered:
        if runs and row.computed_at - runs[-1][-1].computed_at <= RUN_GAP:
            runs[-1].append(row)
        else:
            runs.append([row])
    return runs


def count_runs(times: list[datetime]) -> int:
    """Number of collection runs in a list of snapshot timestamps."""
    ordered = sorted(times)
    runs = 0
    prev: datetime | None = None
    for t in ordered:
        if prev is None or t - prev > RUN_GAP:
            runs += 1
        prev = t
    return runs


def _finite(values: list[float | None]) -> list[float]:
    return [v for v in values if v is not None and not math.isnan(v) and not math.isinf(v)]


def _mean(values: list[float | None]) -> float | None:
    vals = _finite(values)
    return statistics.fmean(vals) if vals else None


def _median(values: list[float | None]) -> float | None:
    vals = _finite(values)
    return statistics.median(vals) if vals else None


def summarize_run(run: list[SnapshotLite]) -> dict:
    by_exp: dict[str, list[SnapshotLite]] = {}
    for r in run:
        by_exp.setdefault(r.experiment, []).append(r)

    experiments = {}
    for name, rows in sorted(by_exp.items()):
        trades_mean = statistics.fmean(r.num_trades for r in rows)
        experiments[name] = {
            "n_pairs": len(rows),
            "trades_total": sum(r.num_trades for r in rows),
            "trades_mean": round(trades_mean, 1),
            "win_rate_mean": _mean([r.win_rate for r in rows]),
            "expectancy_mean": _mean([r.expectancy for r in rows]),
            "sharpe_mean": _mean([r.sharpe for r in rows]),
            "profit_factor_median": _median([r.profit_factor for r in rows]),
            "small_sample": trades_mean < MIN_TRADES_PER_PAIR,
        }

    # Same comparison the Backtests page already shows (22/40): per pair, does the
    # pipeline beat Ichimoku alone on Sharpe?
    pipe = {(r.symbol, r.timeframe): r.sharpe for r in by_exp.get(PIPELINE, [])}
    base = {(r.symbol, r.timeframe): r.sharpe for r in by_exp.get(ICHIMOKU_ONLY, [])}
    compared = [k for k in pipe if k in base and pipe[k] is not None and base[k] is not None]
    beats = sum(1 for k in compared if pipe[k] > base[k])  # type: ignore[operator]

    return {
        "started_at": run[0].computed_at.isoformat(),
        "ended_at": run[-1].computed_at.isoformat(),
        "n_rows": len(run),
        "n_pairs": len({(r.symbol, r.timeframe) for r in run}),
        "experiments": experiments,
        "pipeline_vs_ichimoku": {"beats": beats, "compared": len(compared)},
    }


EXIT_REASONS = {
    "stop_hit": "stop touché",
    "take_profit_hit": "objectif atteint",
    "pipeline_downgraded": "le pipeline est repassé en attente",
}

BLOCK_REASONS = {
    "rsi_overbought_block_long": "RSI en surachat, achat refusé",
    "rsi_oversold_block_short": "RSI en survente, vente refusée",
}

SOURCE_LABEL = {
    "structure": "structure",
    "context": "contexte",
    "fibonacci": "Fibonacci",
}


def _fmt_price(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "?"
    return f"{value:.6g}"


def humanize_journal_event(
    event_type: str, payload: dict, *, symbol: str | None, direction: str | None
) -> dict | None:
    """Turn one paper-journal row into a readable feed item, or None to skip it
    (SHADOW_OPEN only repeats what SHADOW_BLOCKED already said)."""
    sym = symbol or payload.get("symbol") or "?"

    if event_type == "OPENED":
        d = payload.get("direction") or direction or ""
        side = "Achat" if d == "LONG" else "Vente" if d == "SHORT" else "Entrée"
        risk = payload.get("risk_pct")
        risk_txt = f" · risque {risk * 100:.0f} %" if isinstance(risk, (int, float)) else ""
        return {
            "kind": "paper_opened",
            "tone": "neutral",
            "symbol": sym,
            "title": f"{side} automatique {sym}",
            "detail": (
                f"entrée {_fmt_price(payload.get('entry'))} · stop {_fmt_price(payload.get('stop'))}"
                f" · objectif {_fmt_price(payload.get('take_profit'))}{risk_txt}"
            ),
        }

    if event_type == "CLOSED":
        reason = EXIT_REASONS.get(str(payload.get("reason")), str(payload.get("reason") or "sortie"))
        pnl = payload.get("pnl_pct")
        pnl_txt = f" · résultat {pnl * 100:+.2f} %" if isinstance(pnl, (int, float)) else ""
        tone = "good" if isinstance(pnl, (int, float)) and pnl > 0 else "bad"
        return {
            "kind": "paper_closed",
            "tone": tone,
            "symbol": sym,
            "title": f"Sortie {sym}",
            "detail": f"{reason}{pnl_txt}",
        }

    if event_type == "SHADOW_BLOCKED":
        source = SOURCE_LABEL.get(str(payload.get("block_source")), str(payload.get("block_source")))
        reason = BLOCK_REASONS.get(str(payload.get("reason")), str(payload.get("reason") or "?"))
        return {
            "kind": "shadow_blocked",
            "tone": "blocked",
            "symbol": sym,
            "title": f"Trade refusé sur {sym}",
            "detail": f"filtre {source} : {reason}",
        }

    if event_type == "SHADOW_CLOSE":
        pnl_r = payload.get("pnl_r")
        won = isinstance(pnl_r, (int, float)) and pnl_r > 0
        r_txt = f" ({pnl_r:+.2f} R)" if isinstance(pnl_r, (int, float)) else ""
        outcome = "aurait gagné" if won else "aurait perdu"
        return {
            "kind": "shadow_closed",
            "tone": "bad" if won else "good",  # winner refused = the filter cost us; loser refused = it helped
            "symbol": sym,
            "title": f"Verdict du trade refusé {sym}",
            "detail": f"il {outcome}{r_txt} : {EXIT_REASONS.get(str(payload.get('exit_reason')), payload.get('exit_reason'))}",
        }

    return None
