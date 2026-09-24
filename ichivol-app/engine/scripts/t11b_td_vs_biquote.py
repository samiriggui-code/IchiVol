#!/usr/bin/env python3
"""T11b — measure Twelve Data vs biquote on forex/metals (credits counted).

Does **not** change live catalog routing (biquote remains FX/metals provider).

Usage (network + TWELVE_DATA_API_KEY)::

    cd ichivol-app/engine
    .venv/bin/python scripts/t11b_td_vs_biquote.py --out ../../docs/T11B-TD-VS-BIQUOTE.md

Offline / CI dry-run (no HTTP)::

    .venv/bin/python scripts/t11b_td_vs_biquote.py --dry-run --out /tmp/t11b.md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ENGINE = Path(__file__).resolve().parents[1]
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

# Catalog id → Twelve Data slash symbol (not used live for FX/metals).
_TD_SYMBOL: dict[str, str] = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "XAUUSD": "XAU/USD",
    "XAGUSD": "XAG/USD",
}

DEFAULT_SYMBOLS = tuple(_TD_SYMBOL.keys())


@dataclass
class FetchRow:
    symbol: str
    provider: str
    provider_symbol: str
    timeframe: str
    n_bars: int
    wall_ms: float
    credits: int
    volume_type: str | None
    first_time: int | None
    last_time: int | None
    last_close: float | None
    error: str | None = None


def _overlap_stats(a_times: list[int], b_times: list[int]) -> dict[str, Any]:
    sa, sb = set(a_times), set(b_times)
    inter = sa & sb
    return {
        "a_bars": len(sa),
        "b_bars": len(sb),
        "intersection": len(inter),
        "only_a": len(sa - sb),
        "only_b": len(sb - sa),
        "overlap_pct_of_min": (
            round(100.0 * len(inter) / min(len(sa), len(sb)), 2)
            if sa and sb
            else None
        ),
    }


def _fetch_one(
    *,
    symbol: str,
    provider: str,
    provider_symbol: str,
    timeframe: str,
    limit: int,
    dry_run: bool,
) -> tuple[FetchRow, list[Any]]:
    from app.indicators.ichimoku import Candle
    from app.market_data import biquote, twelve_data

    if dry_run:
        # Synthetic closed 1h bars — no credits / no HTTP.
        base = 1_700_000_000
        candles = [
            Candle(
                time=base + i * 3600,
                open=1.0 + i * 0.01,
                high=1.1 + i * 0.01,
                low=0.9 + i * 0.01,
                close=1.05 + i * 0.01,
                volume=0.0 if provider == "twelve_data" else float(i + 1),
            )
            for i in range(min(limit, 120))
        ]
        return (
            FetchRow(
                symbol=symbol,
                provider=provider,
                provider_symbol=provider_symbol,
                timeframe=timeframe,
                n_bars=len(candles),
                wall_ms=0.1,
                credits=1 if provider == "twelve_data" else 0,
                volume_type=candles[-1].volume_type.value if candles else None,
                first_time=candles[0].time if candles else None,
                last_time=candles[-1].time if candles else None,
                last_close=candles[-1].close if candles else None,
            ),
            candles,
        )

    t0 = time.perf_counter()
    credits_before = (
        twelve_data.credits_used_in_window(3600.0) if provider == "twelve_data" else 0
    )
    try:
        if provider == "biquote":
            candles = biquote.fetch_ohlc(provider_symbol, timeframe, limit)
            credits = 0
        else:
            twelve_data.clear_ohlcv_cache()
            candles = twelve_data.fetch_time_series(provider_symbol, timeframe, limit)
            credits = max(
                0, twelve_data.credits_used_in_window(3600.0) - credits_before
            )
        wall_ms = (time.perf_counter() - t0) * 1000.0
        vt = candles[-1].volume_type.value if candles else None
        return (
            FetchRow(
                symbol=symbol,
                provider=provider,
                provider_symbol=provider_symbol,
                timeframe=timeframe,
                n_bars=len(candles),
                wall_ms=round(wall_ms, 2),
                credits=credits,
                volume_type=vt,
                first_time=candles[0].time if candles else None,
                last_time=candles[-1].time if candles else None,
                last_close=candles[-1].close if candles else None,
            ),
            candles,
        )
    except Exception as exc:  # noqa: BLE001 — report per-symbol
        wall_ms = (time.perf_counter() - t0) * 1000.0
        return (
            FetchRow(
                symbol=symbol,
                provider=provider,
                provider_symbol=provider_symbol,
                timeframe=timeframe,
                n_bars=0,
                wall_ms=round(wall_ms, 2),
                credits=0,
                volume_type=None,
                first_time=None,
                last_time=None,
                last_close=None,
                error=str(exc),
            ),
            [],
        )


def run_study(
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
    timeframe: str = "1h",
    limit: int = 300,
    dry_run: bool = False,
) -> dict[str, Any]:
    from app.universe.catalog import get_instrument

    rows: list[FetchRow] = []
    comparisons: list[dict[str, Any]] = []

    for sym in symbols:
        inst = get_instrument(sym)
        bq_sym = inst.provider_symbol if inst and inst.provider_symbol else sym
        td_sym = _TD_SYMBOL.get(sym, sym)

        bq_row, bq_candles = _fetch_one(
            symbol=sym,
            provider="biquote",
            provider_symbol=bq_sym,
            timeframe=timeframe,
            limit=limit,
            dry_run=dry_run,
        )
        td_row, td_candles = _fetch_one(
            symbol=sym,
            provider="twelve_data",
            provider_symbol=td_sym,
            timeframe=timeframe,
            limit=limit,
            dry_run=dry_run,
        )
        rows.extend([bq_row, td_row])
        comparisons.append(
            {
                "symbol": sym,
                "biquote": asdict(bq_row),
                "twelve_data": asdict(td_row),
                "time_overlap": _overlap_stats(
                    [c.time for c in bq_candles],
                    [c.time for c in td_candles],
                ),
                "close_delta_last": (
                    None
                    if bq_row.last_close is None or td_row.last_close is None
                    else round(float(td_row.last_close) - float(bq_row.last_close), 8)
                ),
            }
        )

    td_credits = sum(r.credits for r in rows if r.provider == "twelve_data")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "timeframe": timeframe,
        "limit": limit,
        "symbols": list(symbols),
        "twelve_data_credits_total": td_credits,
        "comparisons": comparisons,
        "recommendation": (
            "Keep live FX/metals on biquote (Phase 1c). Twelve Data remains "
            "equities-only in catalog; use TD only if overlap/quality justifies "
            "the credit cost (T11c decision — human). Dry-run rows are synthetic."
            if dry_run
            else (
                "Keep live FX/metals on biquote unless measured overlap + volume "
                "semantics clearly beat credit cost. No catalog change in T11b."
            )
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# T11b — Twelve Data vs biquote (forex / métaux)",
        "",
        f"Généré : `{report['generated_at']}`  ",
        f"Mode : `{'dry-run (synthétique)' if report['dry_run'] else 'live HTTP'}`  ",
        f"TF : `{report['timeframe']}` · limit `{report['limit']}`  ",
        f"Crédits Twelve Data (session) : **{report['twelve_data_credits_total']}**",
        "",
        "## Méthode",
        "",
        "- Symboles catalogue FX/métaux ; biquote via `provider_symbol` catalogue.",
        "- Twelve Data via forme slash (`EUR/USD`, …) — **hors catalogue live**.",
        "- Aucun changement `catalog.py` / watchlist (T11b partiel).",
        "- Crédits = acquisitions `_try_acquire_credit_slot` (fenêtre moteur).",
        "",
        "## Résultats",
        "",
        "| Symbole | BQ bars | TD bars | Overlap % | Δ close | TD credits | BQ ms | TD ms | Err |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for c in report["comparisons"]:
        bq, td = c["biquote"], c["twelve_data"]
        ov = c["time_overlap"].get("overlap_pct_of_min")
        err = td.get("error") or bq.get("error") or ""
        lines.append(
            f"| {c['symbol']} | {bq['n_bars']} | {td['n_bars']} | "
            f"{ov if ov is not None else '—'} | "
            f"{c['close_delta_last'] if c['close_delta_last'] is not None else '—'} | "
            f"{td['credits']} | {bq['wall_ms']} | {td['wall_ms']} | {err[:40]} |"
        )
    lines.extend(
        [
            "",
            "## Recommandation",
            "",
            report["recommendation"],
            "",
            "## JSON",
            "",
            "```json",
            json.dumps(report, indent=2)[:8000],
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--timeframe", default="1h")
    p.add_argument("--limit", type=int, default=300)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--json-out", type=Path, default=None)
    args = p.parse_args()
    report = run_study(
        timeframe=args.timeframe, limit=args.limit, dry_run=args.dry_run
    )
    md = render_markdown(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(md)
    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
