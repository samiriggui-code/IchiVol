# Research clones (architecture / algorithm reference only — not product runtime)

Vendor trees under this folder are **not** imported by the IchiVol engine.
Production uses clean-room adapters in `engine/app/structure/adapters/`.

## Clones

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
