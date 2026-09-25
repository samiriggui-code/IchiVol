# Handoff — UI-port 11 pages (PR #109)

Branche `cursor/ui-port-pages-a2fe` · **draft** · pas de merge avant relecture Claude + OK Samir.

## État
- 11/11 pages à **0 écart** (compare-maquette.mjs 1440+390) — `docs/ui-port/compare/RAPPORT.md`
- Paper open/close **rebranché** (Opportunités / Marché `?open=1` / Portefeuille)
- `docs/ui-port/ACTIONS-METIER.md` — audit écritures lib/
- Orphelins Claude (17 − 2 sheets paper) **supprimés** + extras `PositionChart` / `VerdictBadge`
- Branche morte `cursor/ui-port-desk-4731` **supprimée**
- Smoke paper open→close : `docs/ui-port/captures/smoke-paper-open-close.json` PASS
- Lab 390 `.metric` : compare mesure maquette **140 px** (pas 127) — app alignée 140

## Flux paper
1. Marché « Préparer le trade → » → `/app/opportunites?symbol=&open=1`
2. Dialog maquette → « Ouvrir une position paper → » → PaperConfirmSheet → openPaperPosition
3. Portefeuille → Fermer → PaperCloseConfirmSheet → closePaperPosition

## Non-merge
Attendre Claude + Samir.
