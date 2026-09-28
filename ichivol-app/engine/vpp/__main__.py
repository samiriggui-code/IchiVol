"""CLI: python -m vpp {download|build|run}."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    cmd = args[0] if args else ""
    if cmd == "download":
        from vpp.data import download

        download()
    elif cmd == "build":
        from vpp.data import build

        build()
    elif cmd == "run":
        from vpp.run import run_all

        run_all()
    elif cmd == "run2":  # amendement VP0-2026-09-28: v1 must already be archived under docs/vpp-artifacts/v1/
        from vpp.run import run_all

        run_all(v2=True, skip_done="--resume" in args)
    elif cmd == "posthoc":  # RS review R3: momentum-matched controls, descriptive only
        import json

        from vpp import U20
        from vpp.data import load_candles
        from vpp.event_study import momentum_matched
        from vpp.paper import paper_costs
        from vpp.run import ART, CONTINUOUS
        from vpp.signals import compute_all

        candles = {s: load_candles(s, "1h")[0] for s in U20}
        out = momentum_matched(compute_all(list(U20)), candles, CONTINUOUS, paper_costs(U20))
        (ART / "vpp_p3_posthoc_momentum.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(json.dumps(out, indent=1))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
