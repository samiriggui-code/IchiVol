# UI-port Marché — handoff

Branche `cursor/ui-port-marche-a2fe` · draft · **pas de merge avant Samir + Claude**.

## Méthode
Port littéral `marche()` + page-head. Données engine. Orphelins supprimés (voir `marche-RETIRES.md`).

## Captures
Voir `docs/ui-port/marche/` (à compléter : maquette vs app 1440/390 full-page + overlay 50%).

## Checklist PR
- [x] ancienne page remplacée, pas de cohabitation
- [x] orphelins supprimés + RETIRES.md
- [x] find-unused-css page (sortie jointe)
- [x] helpers : `fmt*Maq` page-local (pas de nouveau `fmtPrice` générique)
- [x] build OK
- [ ] smoke 11 pages
- [ ] captures + overlay
