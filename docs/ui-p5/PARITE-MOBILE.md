# Parité mobile — UI-P5 (port maquette)

Référence : `design-reference/ichivol-workspace/style.css` `@media(max-width:800px)` et `@media(max-width:1150px)`.

## Marché (cette PR)
- ≤1150 : grille 150px + 1fr ; panneau Lecture passe en pleine largeur sous le graphique.
- ≤800 : une colonne ; watchlist en rangée scrollable (`display:flex; overflow:auto`) ; Lecture empilée sous le graphique.
- **Interdit** : tiroir / drawer / `display:none` qui retire du contenu desktop.
- Captures : `docs/ui-port/marche/app-390.png` + overlay 50 %.

Pages suivantes (Desk, Opportunités, …) : même règle, une PR = une page.
