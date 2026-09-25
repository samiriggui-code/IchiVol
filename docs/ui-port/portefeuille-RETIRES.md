# Portefeuille — éléments retirés (port maquette)

## Fichiers supprimés

| Fichier | Raison |
|---------|--------|
| `pages/PaperPage.tsx` (+ css) | Onglets Compte/Positions hors maquette `portefeuille()` |
| `pages/SynthesePage.tsx` | Onglet Synthèse hors maquette |

## UI retirée vs ancienne page

- Onglets Synthèse / Compte / Positions / Risque / Tests
- Labs paper card / broker equity blocks
- DeskCardShell / allocation rings (Desk) — remplacés par `.donut` + progress maquette

## Champs « — »

| Emplacement | Champ | Note |
|-------------|-------|------|
| Risk Kernel | Risque par trade | Pas de métrique engine exposée telle quelle |
| Exposition globale | plafond `/ 40 %` | Plafond max exposure non lu → `x / —` |
| Positions | STRATEGY / PERFORMANCE | Fallback timeframe ; unrealized null → — |

## Orphelins Claude (relecture PR #109) — supprimés
| Fichier | Raison |
|---------|--------|
| `PaperTradeSheet.tsx` | Détail position hors maquette ; clôture via `PaperCloseConfirmSheet` |
| `BrokerAccount.tsx` / `CostsPanel.tsx` / `TestProgressPanel.tsx` / `ActivityJournal.tsx` / `PortfolioChart.tsx` | Ancienne Synthèse hors maquette |
| Conservé : `PaperCloseConfirmSheet` | Fermeture paper depuis table Positions |
