"""CLI: python -m vp3 run|list — VP3 B* baselines on VP2 harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vp3 import STRATEGIES
from vp3.run import run_strategy


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vp3", description="VP3 B0–B7 entry baselines")
    p.add_argument("--root", type=Path, default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List strategies")

    r = sub.add_parser("run", help="Run one strategy on frozen VP1 series")
    r.add_argument("--strategy", required=True, choices=STRATEGIES)
    r.add_argument("--symbol", default="BTCUSDT")
    r.add_argument("--interval", default="1h", choices=("1h", "4h"))
    r.add_argument("--cost", default="base", choices=("base", "adverse"))
    r.add_argument("--window-start", default=None, help="ISO date override start")
    r.add_argument("--window-end", default=None, help="ISO date override end (inclusive)")

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
    return 2


if __name__ == "__main__":
    sys.exit(main())
