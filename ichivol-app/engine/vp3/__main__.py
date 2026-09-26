"""CLI: python -m vp3 run|wf|list — VP3 B* baselines + walk-forward."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vp3 import STRATEGIES
from vp3.compare import COMPARE_QUESTIONS, compare_question
from vp3.run import run_strategy
from vp3.wf import run_wf


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vp3", description="VP3 B0–B7 entry baselines")
    p.add_argument("--root", type=Path, default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List strategies")

    r = sub.add_parser("run", help="Run one strategy on frozen VP1 series (full window)")
    r.add_argument("--strategy", required=True, choices=STRATEGIES)
    r.add_argument("--symbol", default="BTCUSDT")
    r.add_argument("--interval", default="1h", choices=("1h", "4h"))
    r.add_argument("--cost", default="base", choices=("base", "adverse"))
    r.add_argument("--window-start", default=None, help="ISO date override start")
    r.add_argument("--window-end", default=None, help="ISO date override end (inclusive)")

    w = sub.add_parser("wf", help="Walk-forward §5 test folds (local VP1 data)")
    w.add_argument("--strategy", required=True, choices=STRATEGIES)
    w.add_argument("--symbol", default="BTCUSDT")
    w.add_argument("--interval", default="1h", choices=("1h", "4h"))
    w.add_argument("--cost", default="base", choices=("base", "adverse"))

    c = sub.add_parser("compare", help="Question A/B/H paired Δ (local VP1 data)")
    c.add_argument("--question", required=True, choices=sorted(COMPARE_QUESTIONS))
    c.add_argument("--symbol", default="BTCUSDT")
    c.add_argument("--interval", default="1h", choices=("1h", "4h"))
    c.add_argument("--cost", default="base", choices=("base", "adverse"))
    c.add_argument("--n-trials", type=int, default=1, help="T10b N for DSR")
    c.add_argument("--n-boot", type=int, default=2000)

    args = p.parse_args(argv)
    if args.cmd == "list":
        print(json.dumps(list(STRATEGIES)))
        return 0
    if args.cmd == "run":
        win = None
        if args.window_start and args.window_end:
            win = (args.window_start, args.window_end)
        out = run_strategy(
            args.strategy,
            symbol=args.symbol,
            interval=args.interval,
            cost_profile=args.cost,
            root=args.root,
            window=win,
        )
        print(json.dumps(out.summary(), indent=2))
        return 0
    if args.cmd == "wf":
        report = run_wf(
            args.strategy,
            symbol=args.symbol,
            interval=args.interval,
            cost_profile=args.cost,
            root=args.root,
        )
        print(json.dumps(report.summary(), indent=2, default=str))
        return 0
    if args.cmd == "compare":
        rep = compare_question(
            args.question,
            symbol=args.symbol,
            interval=args.interval,
            cost_profile=args.cost,
            root=args.root,
            n_trials=args.n_trials,
            n_boot=args.n_boot,
        )
        print(json.dumps(rep.summary(), indent=2, default=str))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
