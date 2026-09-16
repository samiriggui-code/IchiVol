# Handoff Claude — Cap produit mis à jour (CDC 2026-09-16)

> **Pour :** Claude (engine / toute session parallèle)  
> **De :** Cursor + utilisateur  
> **Action :** **lire avant** de toucher backlog V2/V3, agents, paper, ou « V2+ »  
> **Doc maître :** [`CAHIER-DES-CHARGES.md`](./CAHIER-DES-CHARGES.md) (maj 2026-09-16)

---

## 1. Ce qui change pour toi

1. **Pas de jalon « V2+ ».** L’échelle officielle est seulement :
   `V1 → V1.5 → V2 → V3 / expérimental → Hors cœur`
2. **Deux couches agents** (déjà dans `HANDOFF-AGENT-CONCEPT.md`, maintenant aussi CDC §2.1) :
   - **StrategyAgents (Python)** = décident (pipeline) — **pas de LLM**
   - **Copilot (TS)** = explique / skills confirmés — **jamais vote** LONG/SHORT
3. **Journal** = page `/app/journal` (Prisma). Aujourd’hui = **snapshot figé**.  
   **V2** = watchlist active + **notifications cloche header** (job serveur / cron — **pas** le LLM qui décide). Spec CDC §6.3.
4. **Option C** (combiner → portes seule vérité) : **toujours non justifiée** par les backtests — rester **Option A** sauf nouvelle preuve.
5. **Multi-marchés** déjà câblés côté front/engine (Binance / Biquote / Twelve Data).  
   Contexte page = **crypto only**. CVD/OI = **crypto**. Paper/watch multi-classe = **après** paper crypto stable (V2).
6. **Live broker** = V3 / après paper + preuve — **jamais** confondre MarketData et Execution.

---

## 2. Backlog moteur / server pertinent pour toi

| Priorité | Item | Note |
|----------|------|------|
| V1.5 UI (Cursor) | Matrice de portes | **Rien à livrer** — `pipeline.stages` déjà OK ; Cursor consomme |
| V2 | Paper crypto | **Déjà livré** (positions + perf) — ne pas casser le contrat |
| V2 | Journal watch + notifs | **À livrer** (souvent **server TS** Prisma, pas engine) — voir §2.1 |
| V2 | Perf / calibration | Après paper stable |
| V2 | Paper multi-classe | **Après** crypto ; même routes, `class` dans universe |
| V2 | Copilot skill décision | Payload chiffré injecté (server agent) — voir §2.1 |
| V3 | Wyckoff / Donchian / ADX | Backtest **avant** vote |
| V3 | Consensus multi-agents | **Seulement après preuve** — pas de multi-personas LLM |

CVD + OI/Funding : déjà cochés moteur — ne pas les faire revoter la direction.

## 2.1 Contrat API — ce que Cursor branche dès que tu livres

**Matrice (fait Cursor) :** aucun nouvel endpoint. Screener / détail déjà avec `pipeline.stages[]`.

**Watch + cloche (livré Cursor 2026-09-16 côté Express/Prisma — tu n’as plus à le refaire) :**

| Endpoint / artefact | Statut |
|---------------------|--------|
| Table Prisma `notifications` + `decisions.watchFingerprint` | ✅ migration `20260916143000` |
| `GET /api/notifications` (+ unreadCount) | ✅ |
| `POST /api/notifications/:id/read` + `read-all` | ✅ |
| Notif à la confirm (+ si gate change au re-confirm) | ✅ |
| Job poll 5 min `startJournalWatchJob` → notif `pipeline_change` | ✅ |
| UI cloche header `NotificationBell` | ✅ |

Optionnel engine : `POST /decisions/batch` si le poll N×1 est trop lent — **pas obligatoire**.

**Paper multi-classe (plus tard) :** mêmes `GET/POST /api/engine/paper/*` ; front enverra symboles hors Binance seulement quand le moteur accepte (documente dans README engine).

**Copilot « Expliquer cette décision » :** skill qui accepte un payload décision (symbol, TF, stages, combiner) — front enverra le snapshot journal / sheet ; **jamais** de vote LONG/SHORT.

---

## 3. Ce que Cursor a déjà fait (ne pas écraser)

- Seuils RVOL/ATR Settings (query params **seulement si ≠ défauts** — sinon screener bypass cache → timeout)
- Backtests + Décisions multi-classe
- Lecture PA / MTF / Location / ATR dans `DecisionPipelinePanel`
- Journal page dédiée + `GET/POST/PATCH /api/decisions`
- CDC réécrit (échelle versions, agents, watch §6.3)

Handoff front détaillé : [`HANDOFF-CURSOR-SESSION-2026-09-16.md`](./HANDOFF-CURSOR-SESSION-2026-09-16.md)

---

## 4. Message court à coller dans Claude

```
Cap produit maj 2026-09-16 — lis docs/CAHIER-DES-CHARGES.md + docs/HANDOFF-CLAUDE-CDC-CAP-2026-09-16.md (§2.1 contrat API front)

- Pas de « V2+ » : seulement V1 → V1.5 → V2 → V3
- StrategyAgents Python décident ; Copilot LLM explique seulement
- Matrice portes = Cursor maintenant (rien à livrer moteur)
- V2 watch+cloche = à livrer server : table Notification + GET/read + job poll confirms → notif si pipeline change (§2.1)
- Paper crypto déjà branché front — ne pas casser /paper/positions|/performance
- Option A ; live broker après paper ; MarketData ≠ Execution
- Ne pas éditer les mêmes fichiers engine en parallèle de Cursor (uvicorn --reload)
```

---

## 5. Fichiers à ouvrir

```
docs/CAHIER-DES-CHARGES.md
docs/HANDOFF-AGENT-CONCEPT.md
docs/HANDOFF-CURSOR-PIPELINE-NATIVE.md   (§7–§10 backtests / Location / Option C)
docs/HANDOFF-CURSOR-SESSION-2026-09-16.md
```
