# Marché — éléments retirés (port maquette)

Branche `cursor/ui-port-marche-a2fe` · rebase sur `main` @ `604a8b0` (#106).

## Supprimés du dépôt (orphelins après portage)

| Fichier | Raison |
|---------|--------|
| `components/BiasPanel.tsx` (+ `.css`) | Lecture technique ≠ panneau maquette |
| `components/MarketWatchlist.tsx` | Screener multi-colonnes ≠ watchlist maquette |
| `components/MarketLayersMenu.tsx` | Calques avancés hors maquette |
| `components/MarkTradeSheet.tsx` | Marquer un trade — hors maquette |
| `components/BacktestOverlaySheet.tsx` | Overlay backtest — hors maquette |
| `pages/market/useMarketController.ts` | Contrôleur terminal #106 — remplacé par page maquette |
| `pages/market/MarketToolbar.tsx` | Toolbar terminal |
| `pages/market/MarketChartArea.tsx` | Zone chart terminal |
| `pages/market/MarketBottomDock.tsx` | Dock bas Backtest/Mark/Journal |
| `pages/market/MarketDrawer.tsx` | Tiroir mobile (interdit) |
| `pages/market/MarketSheets.tsx` | Sheets Mark/Backtest |
| `pages/market/marketHelpers.ts` | Helpers terminal (format bias/scan) |

Conservé : `pages/market/marketMaquetteHelpers.ts` (affichage maquette).

## Prefs retirées (`marketPrefs.ts`)

Drawer / panneau droit / dock bas / sort / classFilter — **supprimés** (plus de clés LS layout).  
Calques : `LAYERS_PREFS_VERSION = 3` · Ichimoku + **Supports/résistances ON** par défaut.

## Ne pas réintroduire

Marquer un trade · Backtest overlay · Calques avancés · screener multi-classes — emplacement futur = décision Samir.
