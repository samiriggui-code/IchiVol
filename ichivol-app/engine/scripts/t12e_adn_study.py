#!/usr/bin/env python3
"""T12e CLI — run ADN matrix on deep_history (or stdin path).

Observation only. Example:

  python -m scripts.t12e_adn_study --symbol BTCUSDT --timeframe 1h --years 2

Writes JSON summary to stdout; optional --md-append path.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python scripts/t12e_adn_study.py` from engine/
_ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))

from app.strategy_lab.adn_ichivol import (  # noqa: E402
    LiveScreenerSettings,
    run_adn_matrix_on_candles,
)
from app.strategy_lab.deep_history import resolve_lab_history  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="T12e ADN IchiVol matrix study")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--timeframe", default="1h")
    p.add_argument("--years", type=float, default=2.0)
    p.add_argument("--rvol-significant", type=float, default=None)
    p.add_argument("--min-oos-trades", type=int, default=30)
    p.add_argument("--train-bars", type=int, default=400)
    p.add_argument("--test-bars", type=int, default=100)
    p.add_argument("--no-refs", action="store_true")
    args = p.parse_args()

    settings = LiveScreenerSettings.production_defaults()
    if args.rvol_significant is not None:
        settings = LiveScreenerSettings.from_mapping(
            {**settings.to_dict(), "rvol_significant": args.rvol_significant},
            source="cli_override",
        )

    try:
        bundle = resolve_lab_history(
            args.symbol,
            args.timeframe,
            deep_history=True,
            years=args.years,
        )
    except Exception as exc:
        print(json.dumps({"error": str(exc), "hint": "Binance/deep_history unavailable"}), flush=True)
        return 2

    report = run_adn_matrix_on_candles(
        bundle.candles,
        symbol=args.symbol,
        timeframe=args.timeframe,
        settings=settings,
        train_bars=args.train_bars,
        test_bars=args.test_bars,
        min_oos_trades=args.min_oos_trades,
        hypothesis_id=f"t12e_adn_{args.symbol}_{args.timeframe}",
        coverage_note=getattr(bundle, "history_warning", None),
        with_references=not args.no_refs,
    )
    print(json.dumps(report.to_dict(), default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
