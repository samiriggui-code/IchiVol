# Research clones (architecture / algorithm reference only — not product runtime)

Vendor trees under this folder are **not** imported by the IchiVol engine.
Production uses clean-room adapters in `engine/app/structure/adapters/` (structure)
and `engine/app/jev/` + `engine/app/eve/` (System One / Ève).

## Structure — trendlines

```bash
cd ichivol-app/research
git clone --depth 1 https://github.com/immortalhowwl/gptheist.git
git clone --depth 1 https://github.com/mvpp/trend-line-detector.git
git clone --depth 1 https://github.com/GregoryMorse/trendln.git
git clone --depth 1 https://github.com/ednunezg/pytrendline.git
```

| Repo | Use for |
|------|---------|
| `gptheist` | Handoff / PASS-VETO / audit / determinism patterns |
| `trend-line-detector` | Fractals + volume-qualified trendlines (compare vs `adapters/mvpp.py`) |
| `trendln` | S/R method comparison (vs `adapters/trendln.py`) |
| `pytrendline` | Pivot/tolerance/breakout comparison (vs `adapters/pytrendline.py`) |

See `docs/ICHIVOL-GPTHEIST-ARCHITECTURE-LAB.md`.

## JEV / jevos-v4 — trading System One (Ève)

```bash
# QuantDinger (chemin Samir)
git clone --depth 1 https://github.com/OpenByteInc/QuantDinger.git OpenByteInc/QuantDinger

cd ichivol-app/research/jev
git clone --depth 1 https://github.com/feder-cr/jev.git feder-cr-jev
git clone --depth 1 https://github.com/jarrodwatts/jev-trader.git jarrodwatts-jev-trader
git clone --depth 1 https://github.com/buberlo/jev-trader.git buberlo-jev-trader
git clone --depth 1 https://github.com/Gamma-Software/jev-signals-lab.git Gamma-Software-jev-signals-lab
# + junction OpenByteInc-QuantDinger → ../../../OpenByteInc/QuantDinger
```

| Repo | Use for |
|------|---------|
| `feder-cr-jev` | jevos-v4 wire format / health / local serve (runtime VPS déjà en place) |
| `jarrodwatts-jev-trader` | Dry-run default, event stream, late→HOLD |
| `buberlo-jev-trader` | Atomic judgments, fallback ladder, hard risk vetoes, Brier/ECE |
| `Gamma-Software-jev-signals-lab` | Multi-question battery + rules in code, paper-only |
| `OpenByteInc-QuantDinger` | Pre-trade Jev gate (`ai_decision_filter.py` — 5 CHOICE atomiques) |

See `docs/EVE-JEV-REPO-RECOVERY-2026-10-16.md` + `docs/HANDOFF-EVE-INTELLIGENCE-V1-2026-10-16.md`.
