# Opérations — éléments retirés (port maquette)

## Fichiers / modules supprimés

| Fichier | Raison |
|---------|--------|
| `pages/activity/activityShared.tsx` | Helpers / CircuitCard / RunDetail hors maquette `operations()` |
| `components/desk/DeskRelocatedCards.tsx` (+ css) | Circuit24 / PipelineHealth / EvidenceOps / MarketPulse / LabsPaper — hors maquette ops ; plus aucun consommateur après port |

## UI retirée vs ancienne page

- Circuit 24 h / Pipeline health / Evidence ops cards
- Filtres historique paper/shadow/backtest
- Timeline backtest runs + RunDetail
- Liens Strategy Lab / métriques summary
- Notice custom hors classes maquette

## Champs « — »

| Emplacement | Champ | Note |
|-------------|-------|------|
| Journal d’audit | lignes | Feed vide → une ligne — |
| Qualité | Doublons | Non exposé engine → — |
| Qualité | Binance / symbole | Screener vide → — ; sinon PASSE/PRUDENCE |
| Qualité | Bougies manquantes | Compte `issue_codes` gap/missing ; sinon 0 |
