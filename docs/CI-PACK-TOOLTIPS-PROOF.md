# CI pack tooltips — preuve non-régression

Branche `cursor/ci-pack-tooltips-a2fe`.

## Ce qui change

- Infobulles **packs** (`BriefingControls`) : couche UI additive (`.ci-pack-tip`), hors SVG.
- `buildObjectTooltip` (lib) : contenu objet pour réutilisation inspector — **pas** de changement `DrawingLayer` / `*Drawing.tsx`.
- `IntelligenceChart` : fallback width/height host (évite calques vides si `timeScale.width()===0`) — pas de `pointer-events` / z-index / clip sur les dessins.
- **Pas** de bouton « ouvrir paper depuis la matrice » (hors exception gel).

## Compteurs objets / pack (filtre = `visibleObjects`)

Fixture 5 objets (structure, fvg, fib, liquidity, S/R) — test `chartIntelligencePacks.test.ts` :

| Pack | Objets visibles (fixture) |
|------|---------------------------|
| calm | structure only via layer map |
| structure | + S/R |
| setup | structure + fib + fvg |
| liquidity | structure + S/R + liquidity |
| full | 5 |

Le test assert que `countVisibleForPack` est stable (même fonction de filtre qu’avant les tooltips).

## Captures

À joindre en review locale (app dev) : BTCUSDT 1h, un screenshot par pack avec infobulle ouverte (hover pack). Automatisation browser non exécutée dans cette PR (session auth).

```bash
npx tsx --test src/lib/chartIntelligencePacks.test.ts
```
