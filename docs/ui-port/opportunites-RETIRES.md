# Opportunités — éléments retirés (port maquette)

## Fichiers supprimés

| Fichier | Raison |
|---------|--------|
| `pages/opportunites/DecisionSheet.tsx` | Hors maquette `opportunites()` ; fiche = `<dialog>` maquette |
| `pages/opportunites/GateStats.tsx` | Hors maquette |
| `pages/opportunites/MethodBanner.tsx` | Hors maquette |
| `pages/opportunites/PipelineRibbon.tsx` | Hors maquette (pipeline textuel dans grille) |
| `pages/opportunites/ScreenerPanel.tsx` | Remplacé par table `.table-wrap` maquette |
| `pages/opportunites/shared.tsx` | Helpers orphelins |
| `pages/opportunites/useOpportunitesController.ts` | Remplacé par logique locale page |
| `pages/opportunites/WhyCard.tsx` | Remplacé par card « Pourquoi X ? » maquette |

## UI retirée vs ancienne page / hors maquette

- Onglets classe d’actif (crypto/forex/…) et filtre Épinglés
- MethodBanner / PipelineRibbon / GateStats / MarketPulseCard
- Sheet mobile DecisionSheet (calques, paper confirm, etc.)
- `decisions-page` / `iv-page-*` / `market-class-tabs`

## Champs maquette affichés « — » (engine)

| Emplacement | Champ | Note |
|-------------|-------|------|
| Matrice | STRUCTURE / EMPLACEMENT / RÉGIME | Si `pipeline.stages` absent |
| Matrice | CYCLE | Si décision non mappable → « — » |
| Matrice | CONFIANCE | Si confidence null |
| Fiche dialog | Déclenchement | Pas de champ engine dédié |
| Fiche dialog | Invalidation | Premier item `invalidation[]` ou « — » |
| Pourquoi X | Carte entière | Si screener vide |

## Orphelins Claude (relecture PR #109) — supprimés
| Fichier | Raison |
|---------|--------|
| `GateMatrix.tsx` | Remplacé par table maquette |
| `ProposePaperTradePanel.tsx` | Flux paper → dialog + `PaperConfirmSheet` |
| `SignalEvidenceCard.tsx` | Hors maquette |
| `TradePlanCard.tsx` | Hors maquette |
| `DecisionPipelinePanel.tsx` | Hors maquette (stats dans dialog) |
