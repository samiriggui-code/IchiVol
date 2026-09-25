# UI-clean — nettoyage front (draft Claude)

Référence visuelle : `design-reference/ichivol-workspace` (maquette), **pas** le zip React-11-pages.

## Objectifs
- CSS mort éliminé ; `index.css` = tokens + shell + composants partagés uniquement
- Pages ≤ ~400 lignes (sections maquette = composants)
- Sections hors-maquette : garder seulement fonctions réelles (paper confirm, kill-switch, Lab avancé…) en bas / onglet Avancé
- Zéro changement comportement (API, routes, auth, tabbar)
- engine/ · server/ intouchés

## Inventaire sections (à compléter au fil des commits)

| Page | Conservé (raison) | Supprimé (raison) |
|---|---|---|
| Desk | KPI, sessions, watch, equity | — |
| Opportunités | ribbon, pourquoi, screener, fiche | — |
| … | … | … |

## Bilan chiffré
Voir `metrics.json` après commits.
