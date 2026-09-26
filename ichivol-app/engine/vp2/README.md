# VP2 — common execution harness

**Protocol:** `docs/VALIDATION-PROTOCOL.md` §1ter, §6, §7 + carte VP2.  
**Simulator:** `research_lab/sim.py` (S1) only.  
**Data:** frozen VP1 spot series (sha256 via manifest).

## Frozen settings

| Champ | Valeur |
|-------|--------|
| Capital | 10 000 |
| Direction | long-only (`allow_short=False`) |
| Fill | next open (`immediate_fill` interdit) |
| Taille | 100 % cash (`full_cash`) · `max_open=1` |
| Stop | ATR(14) × 1.5 de la barre signal |
| TP | 2R |
| Time-stop | 48 barres (1h) / 24 (4h) · exit au **close** |
| Sortie | `exit_mode=levels_only` (pas de flip pipeline) |
| Coûts | `base` / `adverse` (`BASE_COST` / `ADVERSE_COST`) |
| Seed | 7 (ordonnancement) |

B0–B8 entry rules arrive in **VP3**. VP2 only freezes the execution shell.

## Commands (from `ichivol-app/engine`)

```bash
python -m vp2 meta --interval 1h
python -m vp2 smoke --symbol BTCUSDT --interval 1h --cost base
```

## Package

- `rules.common_rules` — §6 / §1ter `Rules`
- `data` — VP1 loader → candles + ATR stop distances
- `run.run_common` — simulate + metadata (seed, sha256, protocol, cost profile)
