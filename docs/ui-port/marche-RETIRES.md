# Marché — éléments retirés de la page (port maquette)

PR : `cursor/ui-port-marche-a2fe` · commit `f731e54`  
Référence maquette : `design-reference/ichivol-workspace` → `marche()` + `page-head` dans `render()`.

Règle : tout ce qui n’est pas dans la maquette sort de la page. Les fichiers orphelins (plus importés nulle part) sont **supprimés** dans cette PR (récupérables via git). Les libs métier restent.

## Supprimés du dépôt (orphelins après retrait de la page)

| Fichier | Raison | Proposition d’emplacement |
|---------|--------|---------------------------|
| `components/BiasPanel.tsx` (+ `.css`) | « Lecture » technique 5 portes / pipeline détaillé ≠ panneau maquette | Opportunités (fiche) ou section repliable ultérieure si Samir le veut |
| `components/MarketWatchlist.tsx` | Screener multi-colonnes (score, contexte, classes) ≠ watchlist maquette (symbole / % / prix) | Opportunités (matrice) — doublon probable |
| `components/MarketLayersMenu.tsx` | Menu Calques avancés (BOS, Fib, FVG, Claude, trades, backtest) | Sous le graphique (menu ⋯) si réintégration demandée |
| `components/MarkTradeSheet.tsx` | « Marquer un trade » T2c | Journal / menu ⋯ graphique |
| `components/BacktestOverlaySheet.tsx` | Overlay backtest T4a | Strategy Lab / menu ⋯ graphique |

## Retiré de l’UI Marché (logique / chrome, pas forcément fichiers dédiés)

| Élément | Raison | Proposition |
|---------|--------|-------------|
| Toolbar symbole / Calques / Indicateurs / Marquer un trade | Hors maquette | Menu ⋯ sur carte graphique (décision Samir) |
| Screener multi-classes + Rescan (Crypto/Forex/…) | Hors maquette | Opportunités ou section « Screener complet » |
| Dock bas Backtest / Marquer / Journal | Hors maquette | Lab / Journal / menu ⋯ |
| Tiroir mobile Liste / Analyse / Backtest | Interdit (tiroir caché) | Empilement maquette ≤800px |
| Prefs layout drawer / right panel / bottom dock | Servaient l’ancien terminal | Conservées dans `marketPrefs.ts` pour non-régression clés LS ; non utilisées par la page |

## Conservé (métier)

- `PriceChart` + overlays Ichimoku / S/R via prefs calques
- `lib/decisions`, `decisionPipeline`, `universe`, `marketPrefs` (calques v2), `agent.confirmAgentAction` (pin watchlist)
- Tokens `camap-tokens` bull/bear alignés maquette (#318d80 / #bf6c61) — partagés, pas page-only

## CSS

- Ancien chrome `.mkt-*` retiré de `index.css` (~14,6 kB).
- Styles page = `MarketPage.css` (port `style.css` maquette, scopé `.market-page`).
