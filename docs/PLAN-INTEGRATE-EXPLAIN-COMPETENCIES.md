# Plan — Intégrer les compétences « evidence pack + tools read-only » dans IchiVol

**Objectif :** piller le *style* et les *mécanismes* de deux refs GitHub, sans copier leur métier ni casser la doctrine IchiVol.  
**Refs clonées :** `_research/stock-insights-mcp`, `_research/fpa-copilot`  
**Doctrine parent :** [`HANDOFF-AGENT-CONCEPT.md`](./HANDOFF-AGENT-CONCEPT.md) · [`AUDIT-AJOUTS-AUTH-DB-AGENT.md`](./AUDIT-AJOUTS-AUTH-DB-AGENT.md)  
**Déjà livré :** `explain_decision` + injection `DECISION_DATA` (voir [`PLAN-COPILOT-EXPLAIN-DECISION.md`](./PLAN-COPILOT-EXPLAIN-DECISION.md))

---

## 0. Phrase fondatrice (inchangée)

```
Score / moteur déterministe  →  evidence pack  →  LLM explain-only (tools read-only)
```

| Couche | Qui | LLM ? |
|--------|-----|-------|
| A. Decision Engine | Python `engine/` | Non |
| B. Copilot | TS `server/src/agent/` | Oui — explique, ne vote pas |

**Interdit :** multi-personas qui votent, XGBoost à la place du pipeline portes, MCP Eve/CRM, ordres broker.

---

## 1. Ce qu’on a analysé

### stock-insights-mcp — « le modèle produit un nombre ; le LLM explique »

| Pattern | Chez eux | Chez IchiVol aujourd’hui |
|---------|----------|---------------------------|
| Verdict hors LLM | XGBoost + SHAP | Pipeline portes + combiner |
| Evidence | 5 tools MCP JSON read-only | `DECISION_DATA` injecté d’un coup |
| LLM | Orchestre tools → prose | Mode `explain_decision` + prompt |

**À piller :** contrats tools read-only, JSON stable + `error`, séparation verdict vs enrichment, tests par tool.  
**À ignorer :** train XGBoost, SHAP, VADER/NewsAPI, filings SEC, framing « should I buy ».

### fpa-copilot — « zéro chiffre inventé ; RAG ne calcule pas »

| Pattern | Chez eux | Chez IchiVol aujourd’hui |
|---------|----------|---------------------------|
| Compute | Tools pandas déterministes | Engine Python |
| Router | Règles → RAG intent → LLM JSON optionnel | Modes UI + question libre |
| RAG | Indexe *résumés d’outils* pour retrouver l’intent | TF-IDF KB Academy (théorie) |
| Multi-tour | `pending_intent` + slots | Historique React volatil |

**À piller :** allowlist d’intents, RAG-as-router (pas as-answer), pending slots, fallback menu, tests routing.  
**À ignorer :** métriques FP&A, CSV/FX, charts Matplotlib, export PDF.

---

## 2. Cible IchiVol (architecture cible)

```
UI (Décisions / Journal / Copilot)
        │  question + (optionnel) decision payload
        v
┌───────────────────────────────────────────────────────────┐
│ Copilot server  POST /api/agent/chat                      │
│  1. Router intent allowlist (fpa pattern)                 │
│  2. Evidence pack = DECISION_DATA (+ LIVE / SCREENER)     │
│  3. Tools read-only optionnels (stock-insights pattern)   │
│  4. KB RAG théorie (existant)                             │
│  5. LLM prose explain-only (jamais re-score / re-vote)    │
│  6. (P5) Actions mutantes → confirm user → execute        │
└───────────────────────────────────────────────────────────┘
        ▲
        │  fetch server-side si tool appelé
        │
┌───────┴────────┐
│ Engine :8000   │  vérité chiffres / stages / portes
└────────────────┘
```

**Règle durcie :** un tool ne **recalcule jamais** un BUY/SELL. Il **récupère** ou **formate** ce que le moteur a déjà produit.

---

## 3. Compétences à intégrer (backlog priorisé)

### Lot A — Evidence pack enrichi (court, fort ROI) — **maintenant / P4-lite**

Élargir `formatDecisionContext` pour un pack plus « SHAP-like » sans ML :

1. **Attribution ordonnée** — stages triés : `fail` → `watch` → `pass`, avec `summary` + `codes`
2. **Drivers** — top raisons / risques / invalidation déjà présents, mis en tête du bloc
3. **Tag sources** — garder `[RAG]` / `[DECISION]` / `[LIVE]` dans le prompt (déjà amorcé)

**Fichiers :** `server/src/agent/context.ts`, `systemPrompt.ts`  
**Critère done :** Expliquer NEARUSDT cite d’abord les portes bloquantes / watch, prose pro (déjà poussée).

### Lot B — Tools read-only allowlist (stock-insights) — **P5-read**

Registry serveur (pas MCP externe obligatoire au MVP) :

| Tool | Entrée | Sortie | Source |
|------|--------|--------|--------|
| `get_decision_detail` | symbol, tf | JSON pipeline + combiner | Engine `/api/engine/decisions/...` |
| `get_live_snapshot` | symbol, tf | bias + RVOL + prix | Engine / snapshot app |
| `get_journal_context` | symbol? | N dernières décisions user | Prisma `Decision` |
| `search_kb` | query | chunks Academy | `knowledge/retriever.ts` (existant) |

Contraintes (volées à stock-insights) :
- `readOnly: true` sur chaque tool
- retour `{ ok, data }` ou `{ ok:false, error }` — jamais de prose
- tools testables sans LLM
- le LLM **ne peut pas** inventer un tool hors liste

**Fichiers :** nouveau `server/src/agent/tools/` + branchement provider function-calling *ou* orchestration manuelle (call tools avant le chat si intent détecté).  
**MVP sans function-calling :** router intent → server appelle tool(s) → injecte résultat dans le prompt (plus simple, style fpa).

### Lot C — Router intent (fpa) — **P4/P5**

Trois étages :

1. **Règles** — synonymes trading (`expliquer`, `pourquoi ce BUY`, `RVOL`, `porte participation`…)
2. **RAG-router** (optionnel) — indexer des *résumés* de décisions/screener (pas la KB théorie) pour retrouver intent + params
3. **LLM router JSON** (optionnel, `temperature: 0`) — `{ intent, params }` uniquement

Intents allowlist initiaux :

| Intent | Mode / tool | Mute ? |
|--------|-------------|--------|
| `explain_decision` | `get_decision_detail` + prose | Non |
| `explain_signal` | `get_live_snapshot` + prose | Non |
| `research` | `search_kb` + prose | Non |
| `trade_idea` | screener block + prose | Non |
| `save_decision` | action | **Oui → confirm** |
| `pin_symbol` | action | **Oui → confirm** |
| `fallback` | menu guidé (comme fpa) | Non |

**Fichiers :** `server/src/agent/planner.ts` (nouveau), `route.ts`  
**Tests :** table de questions → intent attendu (miroir `fpa-copilot/tests/test_agent.py`).

### Lot D — Pending slots + threads (fpa + audit P3) — **P3**

- Persister `agent_threads` / `agent_messages` (déjà spec dans audit)
- Session slots : `pending_intent`, `assumed_symbol`, `assumed_tf` (ex. « explique » après avoir ouvert BTCUSDT)
- Ne pas re-fetcher le monde si le symbole est déjà dans le thread

### Lot E — Actions confirmées (audit P5) — **après Lot B/C**

- Tools mute hors allowlist = refus
- Proposition → UI confirm → `actions` + `audit_log`
- **Aucun** tool d’exécution broker

---

## 4. Mapping fichiers IchiVol

| Zone | Action |
|------|--------|
| `server/src/agent/context.ts` | Lot A — evidence pack enrichi |
| `server/src/agent/systemPrompt.ts` | Mentioner tools/evidence ; garder INTERDIT vote |
| `server/src/agent/planner.ts` | **Nouveau** — Lot C |
| `server/src/agent/tools/*.ts` | **Nouveau** — Lot B |
| `server/src/agent/route.ts` | Brancher planner + tools → prompt |
| `server/prisma/schema.prisma` | Lot D — `AgentThread` / `AgentMessage` |
| `src/lib/agentSession.tsx` / `AgentPanel.tsx` | Pending slots UI + confirm actions |
| `_research/*` | Lecture seule — **ne pas importer** dans le build app |

---

## 5. Phases d’exécution (ordre recommandé)

| Phase | Contenu | Dépend de |
|-------|---------|-----------|
| **E0** | Ce plan + clones en `_research/` | — ✅ |
| **E1** | Lot A evidence pack (context.ts) | E0 ✅ (2026-09-16) |
| **E2** | Lot B tools read-only + injection server-side (sans FC) | E1 ✅ (2026-09-16) |
| **E3** | Lot C router règles + tests | E2 ✅ (2026-09-16) |
| **E4** | Lot D threads DB + pending slots | Audit P3 ✅ (2026-09-16) |
| **E5** | Lot E actions confirm | Audit P5 ✅ (2026-09-16) |

Alignement audit existant : E4 ≈ P3, E2/E3 ≈ P4-lite, E5 ≈ P5.

---

## 6. Hors scope (ne pas faire)

- Remplacer le Decision Engine par un modèle ML
- Brancher un MCP Claude Desktop comme runtime prod (OK en lab ; prod = tools internes Express)
- Copier Eve CRM (queue autonome, `record_fact`, agent builder)
- TradingAgents / multi-agents bull-bear
- Mémoire Tencent / GSMS

---

## 7. Critères de succès

- [ ] Copilot explique toujours à partir d’un pack structuré (jamais recalcul direction)
- [ ] Au moins 3 tools read-only unit-testés sans clé LLM
- [ ] Question ambiguë → menu `fallback`, pas un faux BUY
- [ ] Tool mute → demande confirmation UI
- [ ] Docs CDC / handoff agent : cases E1–E3 cochées

---

## 8. Prochaine action concrète

**E1–E5 ✅** — evidence pack → tools → planner → threads → actions confirm + audit.

Plan d’intégration Copilot competencies **terminé** pour ce lot.
