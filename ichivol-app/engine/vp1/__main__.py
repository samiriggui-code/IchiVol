"""CLI: python -m vp1 download-spot|download-funding|build-spot|verify"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vp1.download import (
    data_root,
    download_funding,
    download_metrics_oi,
    download_spot_klines,
)
from vp1 import SPOT_INTERVALS, SYMBOLS
from vp1.load import build_spot_series, verify_manifest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vp1", description="VP1 Vision data + frozen manifest")
    p.add_argument("--root", type=Path, default=None, help="data root (default: vp1/data)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("download-spot", help="Download spot monthly klines (1h/4h/1d)")
    sub.add_parser("download-funding", help="Download perp monthly fundingRate")
    m = sub.add_parser("download-oi", help="Download perp daily metrics (OI) — many files")
    m.add_argument("--symbol", default=None, help="Limit to one symbol")

    b = sub.add_parser("build-spot", help="Build frozen spot series JSON from raw zips")
    b.add_argument("--symbol", default=None)
    b.add_argument("--interval", default=None)

    sub.add_parser("verify", help="Verify all non-missing manifest sha256")

    args = p.parse_args(argv)
    root = data_root(args.root)

    if args.cmd == "download-spot":
        man = download_spot_klines(root)
        n = sum(1 for e in man["files"].values() if e.get("kind") == "spot_klines_monthly" and not e.get("missing"))
        print(f"spot klines ok/cached entries: {n}")
        return 0
    if args.cmd == "download-funding":
        man = download_funding(root)
        n = sum(1 for e in man["files"].values() if e.get("kind") == "futures_funding_monthly" and not e.get("missing"))
        print(f"funding ok/cached entries: {n}")
        return 0
    if args.cmd == "download-oi":
        syms = (args.symbol,) if args.symbol else SYMBOLS
        man = download_metrics_oi(root, symbols=syms)
        n = sum(1 for e in man["files"].values() if e.get("kind") == "futures_metrics_daily" and not e.get("missing"))
        print(f"metrics OI ok/cached entries: {n}")
        return 0
    if args.cmd == "build-spot":
        syms = (args.symbol,) if args.symbol else SYMBOLS
        ivs = (args.interval,) if args.interval else SPOT_INTERVALS
        for s in syms:
            for iv in ivs:
                entry = build_spot_series(root, s, iv)
                print(s, iv, entry.get("n_rows"), entry.get("sha256", "")[:12])
        return 0
    if args.cmd == "verify":
        errs = verify_manifest(root)
        if errs:
            print("FAIL", *errs, sep="\n")
            return 1
        print("OK")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
