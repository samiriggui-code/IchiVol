"""Batch A/B/H compares for VP-GRID1 → JSON lines (local VP1 data)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from vp3.compare import compare_question

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
INTERVALS = ("1h", "4h")
QUESTIONS = ("A", "B", "H")


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/vp3_grid_results.jsonl")
    n_boot = int(sys.argv[2]) if len(sys.argv) > 2 else 10_000
    out_path.write_text("", encoding="utf-8")  # truncate — avoid append duplicates on relaunch
    results: list[dict] = []
    for symbol in SYMBOLS:
        for interval in INTERVALS:
            for q in QUESTIONS:
                print(f"RUN {q} {symbol} {interval} n_boot={n_boot}", flush=True)
                rep = compare_question(
                    q,
                    symbol=symbol,
                    interval=interval,
                    cost_profile="base",
                    n_trials=1,
                    n_boot=n_boot,
                )
                summary = rep.summary()
                results.append(summary)
                with out_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(summary, default=str) + "\n")
                print(
                    f"  beats={summary['bi_beats_bj']} "
                    f"{summary['score_i']['strategy']} n={summary['score_i']['n_trades']} "
                    f"exp={summary['score_i']['expectancy']} dsr={summary['score_i']['dsr']}",
                    flush=True,
                )
    out_path.with_suffix(".json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"WROTE {out_path} and {out_path.with_suffix('.json')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
