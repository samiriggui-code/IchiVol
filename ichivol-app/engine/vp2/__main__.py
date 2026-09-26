"""CLI: python -m vp2 smoke|meta — VP2 common harness (no B* strategies)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vp2 import DEFAULT_SEED, INITIAL_CAPITAL, PROTOCOL_VERSION
from vp2.rules import common_rules
from vp2.run import run_common


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vp2", description="VP2 common execution harness")
    p.add_argument("--root", type=Path, default=None, help="VP1 data root")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("smoke", help="Run flat harness (no entries) on frozen VP1 series")
    s.add_argument("--symbol", default="BTCUSDT")
    s.add_argument("--interval", default="1h", choices=("1h", "4h"))
    s.add_argument("--cost", default="base", choices=("base", "adverse"))
    s.add_argument("--seed", type=int, default=DEFAULT_SEED)

    m = sub.add_parser("meta", help="Print frozen Rules + protocol metadata as JSON")
    m.add_argument("--interval", default="1h", choices=("1h", "4h"))

    args = p.parse_args(argv)

    if args.cmd == "meta":
        r = common_rules(args.interval)
        print(
            json.dumps(
                {
                    "protocol_version": PROTOCOL_VERSION,
                    "interval": args.interval,
                    "initial_capital": INITIAL_CAPITAL,
                    "exit_mode": r.exit_mode,
                    "time_stop_bars": r.time_stop_bars,
                    "bar_seconds": r.bar_seconds,
                    "full_cash": r.full_cash,
                    "allow_short": r.allow_short,
                    "immediate_fill": r.immediate_fill,
                    "max_open": r.max_open,
                    "take_profit_r": r.take_profit_r,
                    "force_flat_at_end": r.force_flat_at_end,
                },
                indent=2,
            )
        )
        return 0

    if args.cmd == "smoke":
        run = run_common(
            symbol=args.symbol,
            interval=args.interval,
            cost_profile=args.cost,
            seed=args.seed,
            root=args.root,
        )
        print(json.dumps(run.summary(), indent=2))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
