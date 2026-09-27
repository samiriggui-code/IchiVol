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
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
