# Desk — éléments retirés (port maquette)

Branche `cursor/ui-port-desk-4731`.

## Fichiers supprimés (orphelins après portage)

| Fichier | Raison |
|---------|--------|
| `pages/desk/AllocationSection.tsx` | Intégré dans `OverviewPage.tsx` (DOM maquette) |
| `pages/desk/EquitySection.tsx` | Idem — trajectoire + segmented |
| `pages/desk/EventsSection.tsx` | Idem — timeline / contrôle / système |
| `pages/desk/KpiSection.tsx` | Idem — `.metrics` / `.metric` |
| `pages/desk/SessionsSection.tsx` | Idem — `.desk-overview` |
| `pages/desk/WatchSection.tsx` | Idem — opportunités + positions + risque |
| `pages/desk/CardShell.tsx` | Remplacé par `section.card` / `.card-head` maquette |

Conservé : `pages/desk/deskFormat.ts`.

## UI retirée vs maquette / ancienne page

- Bouton **Actualiser** (hors maquette `desk()` page-head)
- Classes `iv-page-*`, `overview-page`, `ov-*`, `desk-kpis`, `desk-grid-2`, `panel` / `panel-head`
- Bannières `banner error` (remplacées par `.notice` maquette si erreur / fraîcheur)
- Badge maquette **DÉMO** → **LIVE** / **—** selon screener
- Texte démo inventé (TONUSDT 2 h, scores 89/82/78 fixes, capital 5 000 €, etc.)

## Champs maquette affichés « — » (engine sans donnée)

| Emplacement | Champ maquette | Source absente / partielle |
|-------------|----------------|----------------------------|
| Lecture du marché | Volatilité | Pas de série vol dédiée |
| Lecture du marché | Régime (h3) | Fear & Greed si dispo, sinon — |
| Marchés principaux | Variation 24h | Si Binance tickers KO |
| À surveiller | Liste / score | Si aucun BUY/SELL screener |
| Trajectoire | Courbe / drawdown | Si `equity_curve` vide |
| Positions | PERFORMANCE | Si `unrealized_pct` null |
| Positions | STRATÉGIE | Fallback timeframe ; pas de nom stratégie API |
| Budget risque | Barres | Si `risk` overview absent |
| Concentration | Anneau / lignes | Si aucune position valorisée |
| État système | Source | Si engine down et screener vide |
| Notice fraîcheur | (omit) | Affichée seulement si stale / mark périmé |
