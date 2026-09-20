"""Do more confluences actually give better signals? Group the measured
signals by how many gates agreed, and compare what happened next.

Pure (no DB): the endpoint builds `OutcomeRow`s from stored records.
Groups are nested on purpose -- each adds one condition to the previous one --
which is the comparison the project is built to answer (Ichimoku alone vs
+ RVOL vs + structure vs the full pipeline)."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Callable

# Below this many signals per group an average is noise, not evidence.
MIN_N = 30
REPORT_HORIZONS: tuple[int, ...] = (5, 10, 20)


@dataclass(frozen=True)
class OutcomeRow:
    direction: str
    decision: str
    stages: dict[str, str]
    asset_class: str
    forward_returns: dict[str, float | None]
    mfe_pct: float | None = None
    mae_pct: float | None = None
    first_of_run: bool = True


def _pass(row: OutcomeRow, stage: str) -> bool:
    return row.stages.get(stage) == "pass"


GROUPS: list[tuple[str, str, Callable[[OutcomeRow], bool]]] = [
    ("ichimoku", "Ichimoku seul", lambda r: True),
    ("rvol", "+ RVOL (participation validée)", lambda r: _pass(r, "participation")),
    (
        "rvol_structure",
        "+ RVOL + structure",
        lambda r: _pass(r, "participation") and _pass(r, "structure"),
    ),
    ("pipeline", "Pipeline validé (achat/vente)", lambda r: r.decision in ("BUY", "SELL")),
]


def _summarize_group(rows: list[OutcomeRow]) -> dict:
    horizons = {}
    for h in REPORT_HORIZONS:
        vals = [r.forward_returns.get(str(h)) for r in rows]
        vals = [v for v in vals if v is not None]
        horizons[str(h)] = {
            "n": len(vals),
            "mean_return": statistics.fmean(vals) if vals else None,
            "median_return": statistics.median(vals) if vals else None,
            "hit_rate": (sum(1 for v in vals if v > 0) / len(vals)) if vals else None,
            "small_sample": len(vals) < MIN_N,
        }
    mfe = [r.mfe_pct for r in rows if r.mfe_pct is not None]
    mae = [r.mae_pct for r in rows if r.mae_pct is not None]
    return {
        "n_signals": len(rows),
        "horizons": horizons,
        "mean_mfe": statistics.fmean(mfe) if mfe else None,
        "mean_mae": statistics.fmean(mae) if mae else None,
    }


def summarize_outcomes(rows: list[OutcomeRow], *, first_of_run_only: bool = True) -> dict:
    used = [r for r in rows if r.first_of_run] if first_of_run_only else list(rows)
    return {
        "min_n": MIN_N,
        "first_of_run_only": first_of_run_only,
        "n_total": len(rows),
        "n_used": len(used),
        "groups": [
            {"id": gid, "label": label, **_summarize_group([r for r in used if pred(r)])}
            for gid, label, pred in GROUPS
        ],
    }
