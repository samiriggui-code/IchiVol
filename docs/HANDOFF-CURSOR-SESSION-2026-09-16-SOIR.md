# Handoff — session Cursor (2026-09-16 soir)

> **Pour :** Claude (engine) + prochaine session Cursor (front / Express)  
> **De :** Cursor  
> **Suite de :** [`HANDOFF-CURSOR-SESSION-2026-09-16.md`](./HANDOFF-CURSOR-SESSION-2026-09-16.md), Cap [`HANDOFF-CLAUDE-CDC-CAP-2026-09-16.md`](./HANDOFF-CLAUDE-CDC-CAP-2026-09-16.md)  
> **Doc maître :** [`CAHIER-DES-CHARGES.md`](./CAHIER-DES-CHARGES.md)  
> **Ports :** Vite `5173` → Express `8787` → engine `8000`

---

## 1. Décisions produit (inchangées)

| Sujet | Statut |
|-------|--------|
| Option A (badge combiner + portes sheet) | Conservée |
| Option C | Non justifiée |
| Copilot = explique, **jamais** vote LONG/SHORT | Verrouillé |
| StrategyAgents Python = décision | Verrouillé |
| Live broker | V3 seulement |
| stock-insights-mcp / Scout MCP | **Évalués puis écartés** comme dépendance produit (data yfinance/NewsAPI pas live ; Scout OK comme *pattern* tools-only, pas à fork) |

---

## 2. Livré cette session (Cursor)

### V1.5 — Matrice de portes
- Décisions : onglets **Liste | Matrice**
- `GateMatrix` : symbole × Dir/Part/Struct/Loc/Risque + verdict portes + badge combiner
- Screener row type étendu : `pipeline?` (déjà renvoyé par le moteur)
- Fichiers : `src/components/GateMatrix.tsx`, `DecisionsPage.tsx`, `decisionPipeline.ts` (`PIPELINE_STAGE_ORDER`, `stageStatusesFromRow`), `decisions.ts`, CSS

### V2 — Journal watch + cloche
- Prisma : `notifications` + `decisions.watchFingerprint` — migration `20260916143000_notifications_watch`
- API : `GET /api/notifications`, `POST …/:id/read`, `POST …/read-all`
- Notif à la confirm journal (+ si gate change au re-confirm)
- Job Express `startJournalWatchJob` : poll confirms toutes les **5 min** → `pipeline_change` si fingerprint change
- UI : `NotificationBell` dans le header (badge unread + inbox)
- Fichiers : `server/src/notifications/*`, `server/src/decisions/route.ts`, `server/src/index.ts`, `src/components/NotificationBell.tsx`, `src/lib/notifications.ts`

**Ops :** si `prisma generate` EPERM → stopper Express `:8787`, `npx prisma generate`, relancer. Déjà fait une fois ; le serveur log `[watch] journal poll every 300s`.

### V2 — Copilot « Expliquer cette décision »
- Mode serveur `explain_decision` + payload `decision` (combiner, direction, gate, stages, reasons…)
- Prompt : explique `DECISION_DATA` ; **interdit** de voter / corriger le moteur
- Client : `decisionPayloadFromDetail`, `AgentSessionProvider`, ouverture bulle auto
- Boutons **Expliquer** : sheet Décisions + ligne Journal (fetch détail puis open)
- Fichiers : `server/src/agent/{types,validate,context,systemPrompt,route}.ts`, `src/lib/agent.ts`, `agentSession.tsx`, `AgentChat.tsx`, `AgentPanel.tsx`, pages Décisions/Journal

Plan écrit : [`PLAN-COPILOT-EXPLAIN-DECISION.md`](./PLAN-COPILOT-EXPLAIN-DECISION.md)

### Settings LLM — table connexions
- User a déjà OpenRouter (`.env` + éventuelle clé UI) — **ne pas** redemander la clé
- `toPublicSettings` expose `llmConnections[]` (openrouter / anthropic / openai : connected, keySource ui|env|both|none, active, model)
- Settings UI : table **LLM connectés** (3 providers), pas un faux « configure ta clé »
- Message agent 400 clarifié si aucune clé résolue

---

## 3. Backlog restant (CDC)

| Priorité | Item | Qui |
|----------|------|-----|
| V2 | Paper multi-classe (forex/métaux/actions) | Claude engine + Cursor UI après |
| V2 optionnel | Graphe corrélations | Claude calcul + Cursor UI |
| V2 soft | Page `/app/agent` + threads | Plus tard (P3 audit) |
| V3 | Wyckoff / Donchian (backtest avant vote) | Claude |
| — | Option B badge = `pipeline.decision` | Cursor quand produit le veut |

**ADX** déjà promu gate régime côté moteur (CDC à jour) — front lit déjà `regime` dans le pipeline.

---

## 4. Pour Claude (ne pas écraser)

1. **Ne pas** refaire Matrice / watch / explain_decision / table LLM — Cursor a livré (§2 + Cap §2.1).
2. Paper crypto stable → ensuite accepter paper hors Binance (documente README engine).
3. Optionnel engine : `POST /decisions/batch` si le poll N×1 du watch devient lent.
4. Ne pas éditer les mêmes fichiers engine en parallèle de Cursor (`uvicorn --reload`).
5. **Doctrine MCP externes :** patterns « tools read-only + LLM explique » OK à s’inspirer ; **ne pas** importer TradingAgents / LLM_trader / agentic-trading-mcp (exécution / vote). Scout = data-only OK ; pas une dépendance IchiVol.

### Message court à coller

```
Handoff Cursor 2026-09-16 soir — lis docs/HANDOFF-CURSOR-SESSION-2026-09-16-SOIR.md + CDC

Livré front/Express : Matrice portes, Journal watch+cloche, explain_decision, table LLM connections
Ne pas écraser. Suite moteur utile : paper multi-classe ; batch decisions optionnel
Pas de « V2+ ». Copilot n’a jamais le droit de vote. ADX déjà en gate régime.
```

---

## 5. Runtime / pièges

1. Seuils RVOL/ATR : **ne pas** renvoyer les défauts sur `/screener` (bypass cache → timeout).
2. Express `:8787` — Prisma generate nécessite arrêt du process Windows (lock DLL).
3. OpenRouter déjà dans `server/.env` — `llmReady` / table Settings doivent le montrer.
4. Equity Twelve Data : pas de scan masse ; détail au clic.

---

## 6. Fichiers touchés (session)

```
ichivol-app/src/components/GateMatrix.tsx
ichivol-app/src/components/NotificationBell.tsx
ichivol-app/src/components/AgentChat.tsx
ichivol-app/src/components/AgentPanel.tsx
ichivol-app/src/layouts/DashboardShell.tsx
ichivol-app/src/pages/DecisionsPage.tsx
ichivol-app/src/pages/JournalPage.tsx
ichivol-app/src/pages/SettingsPage.tsx
ichivol-app/src/lib/{agent,agentSession,notifications,decisions,decisionPipeline,settings}.ts(x)
ichivol-app/src/index.css
ichivol-app/server/prisma/schema.prisma
ichivol-app/server/prisma/migrations/20260916143000_notifications_watch/
ichivol-app/server/src/notifications/{create,route,watch}.ts
ichivol-app/server/src/agent/{types,validate,context,systemPrompt,route}.ts
ichivol-app/server/src/settings/{types,resolve}.ts
ichivol-app/server/src/{index,decisions/route}.ts
docs/CAHIER-DES-CHARGES.md
docs/HANDOFF-CLAUDE-CDC-CAP-2026-09-16.md
docs/PLAN-COPILOT-EXPLAIN-DECISION.md
```

---

## 7. Prochaine action Cursor (si on enchaîne)

1. ✅ Watch branché sur `POST /decisions/batch` (SOIR2 Claude).  
2. UI graphe corrélations (Contexte / Marché) — moteur `GET /correlations` prêt.  
3. Smoke : Confirm → notif ; watch fingerprint ; Expliquer → bulle.  
4. Paper multi-marchés déjà OK côté moteur + textes front.
