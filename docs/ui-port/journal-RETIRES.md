# Journal — éléments retirés (port maquette)

## Fichiers / modules supprimés

| Fichier | Raison |
|---------|--------|
| `pages/journal/journalFormat.ts` | Helpers d’ancienne UI ; formats réintégrés inline dans `JournalPage.tsx` |

## UI retirée vs ancienne page

- En-tête custom (`iv-page-header` / `market-head` / liens Portefeuille·Opérations)
- Onglet « Archivées » + toggle archive / restaurer / supprimer
- Actions par ligne (Actualiser, Expliquer, Retirer, Supprimer)
- Colonnes Confirmé / MAJ / TF / Brut / Portes / RVOL
- `ConfirmDialog` de suppression / archivage
- Panneau détail décision (replay engine `getDecisionDetail` + Copilot explain)
- Note liée à une décision sélectionnée (remplacée par note session maquette `localStorage`)

## Champs « — »

| Emplacement | Champ | Note |
|-------------|-------|------|
| Tableau Trades | RÉSULTAT (R) | Pas de R multiple si `risk_amount` / `realized_pnl` absents |
| Tableau Trades | PERFORMANCE / SORTIE | `pnl_pct` / `exit_reason` null → — |
| Tableau Décisions | RÉSULTAT / PERFORMANCE | Non exposés côté décisions user → — |
| Rejouer une décision | eyebrow / titre / corps | Aucun trade/décision → — ; corps toujours — (pas de prose engine) |
| Note personnelle | — | Persistée navigateur (`ichivol-note`), hors engine |
