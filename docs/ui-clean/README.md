# UI-clean — nettoyage front (draft Claude)

Référence visuelle : `design-reference/ichivol-workspace` (maquette), **pas** le zip React-11-pages.

## Objectifs
- CSS mort éliminé ; `index.css` = tokens + shell + composants partagés uniquement
- Pages ≤ ~400 lignes (sections maquette = composants)
- Sections hors-maquette : garder seulement fonctions réelles (paper confirm, kill-switch, Lab avancé…) en bas / onglet Avancé
- Zéro changement comportement (API, routes, auth, tabbar)
- engine/ · server/ intouchés

## Inventaire sections

| Page | Conservé (raison) | Supprimé (raison) |
|---|---|---|
| Desk | KPI, sessions, watch, equity, allocation, events (`pages/desk/`) | — (déjà découpé ee3a35c) |
| Opportunités | MethodBanner, PipelineRibbon, WhyCard, GateStats, ScreenerPanel, DecisionSheet (`pages/opportunites/`) + controller | — ; `?symbol=` / `decisions-chrome` / sheet mobile inchangés |
| Marché | Toolbar, ChartArea, BottomDock, Drawer, Sheets (`pages/market/`) + controller | — ; calques / marquage / backtest overlay inchangés |
| Lab | LabKpis, LabMainContent, HistorySheet, labShared (`pages/lab/`) + controller | — ; onglets compare/régimes/expériences/live/research inchangés |
| Paramètres | Tab panels LLM / Connexions / Marché / Alertes / Risque / Environnement (`pages/settings/`) | — ; nav locale + confirm clés inchangés |
| Journal | Helpers `journal/journalFormat` (fmt, CSV) | — ; panels lourds reportés (page encore >400) |
| Activité | Helpers + CircuitCard / RunDetail (`activity/activityShared`) | — ; page encore >400 |
| CSS index | Tokens, shell, agent, synthèse, paper, shared components | Blocs page-only déplacés → DecisionsPage.css / MarketPage.css / SettingsPage.css (Phone Décisions, propose paper, Settings nav, UI-MARKET layout) |

## Bilan chiffré
Voir `metrics.json` après commits.
