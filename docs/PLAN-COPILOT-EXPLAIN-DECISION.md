# Plan — Copilot « Expliquer cette décision » (V2)

**Objectif :** brancher le skill CDC sur Décisions + Journal, en réutilisant le Copilot flottant existant.  
**Hors scope immédiat :** page `/app/agent` + threads (P3) ; paper multi-marchés (phase suivante).

---

## Contexte

Aujourd’hui le Copilot a 3 modes : `explain_signal` / `research` / `trade_idea`.  
`explain_signal` = snapshot **Marché** (bias bull/bear + RVOL), **pas** le pipeline Decision Engine.

Manque :
- mode `explain_decision` + payload structuré (symbol, TF, combiner, portes, stages)
- ouverture agent depuis Décisions / Journal
- règle prompt : expliquer le verdict existant, **jamais** voter LONG/SHORT

---

## Approche retenue

**Nouveau mode `explain_decision`** (pas d’overload de `explain_signal`) — contrat clair, validation séparée.

**Provider React `AgentSession`** (à côté de `MarketSnapshot`) :
- `openWithDecision(detail)` → ouvre le chat, mode `explain_decision`, envoie automatiquement une 1ʳᵉ question
- Décisions / Journal n’ont pas besoin d’être sur Marché

Journal : au clic → `getDecisionDetail(symbol, interval)` puis `openWithDecision` (même pattern que Actualiser).

---

## Contrat payload (server)

```ts
mode: 'explain_decision'
decision: {
  symbol, timeframe, price?,
  combiner: DecisionLabel,      // STRONG_BUY…
  direction: LONG|SHORT|NEUTRAL,
  gateDecision?: BUY|SELL|WATCH|NO_TRADE,
  confidence?, rvol?,
  reasons[], risks[], invalidation[],
  stages: [{ id, status, summary, codes? }]
}
```

Chiffres injectés côté serveur via `formatDecisionContext` → bloc `DECISION_DATA` (même pattern que `LIVE_DATA`).

Prompt mode :
- Explique **pourquoi** le moteur a sorti ce verdict (combiner + portes + stages).
- Cite uniquement `DECISION_DATA` + KB.
- **Interdit** : nouvelle reco LONG/SHORT/BUY/SELL qui contredit ou « corrige » le moteur.

---

## Fichiers à toucher

| Zone | Fichiers |
|------|----------|
| Server | `agent/types.ts`, `validate.ts`, `context.ts`, `systemPrompt.ts`, `route.ts` |
| Client API | `src/lib/agent.ts` (+ helper `decisionPayloadFromDetail`) |
| Session UI | nouveau `src/lib/agentSession.tsx` ; `AgentChat.tsx` / `AgentPanel.tsx` ; wrap dans `DashboardShell` |
| Entrées | `DecisionsPage.tsx` (bouton à côté de Confirmer) ; `JournalPage.tsx` (bouton Expliquer) |
| Docs | cocher CDC V2 Copilot ; maj courte handoff Cap §2.1 |

**Pas** de nouvelle page `/app/agent` dans ce lot.

---

## UX

1. Clic **Expliquer** → bulle agent s’ouvre, mode « Décision », 1ʳᵉ réponse auto.
2. Mode visible dans les onglets du panel (4ᵉ mode, actif seulement si payload décision présent).
3. Header panel : `Agent · BTCUSDT · 1h`.

---

## Tests manuels

- [ ] Décisions : ouvrir sheet crypto → Expliquer → réponse cite stages / portes
- [ ] Journal : Expliquer sur une ligne → même flux (fetch détail)
- [ ] Sans clé LLM → erreur claire (comportement actuel)
- [ ] Mode ne propose pas un nouveau LONG/SHORT (spot-check prompt)

---

## Suite (pas dans ce plan)

- Paper multi-marchés (dépend moteur)
- Graphe corrélations
- Threads `/app/agent`
