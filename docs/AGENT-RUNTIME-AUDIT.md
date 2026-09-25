# Audit — Agent Runtime IchiVol × Comp AI / Eve

**Date** : 2026-09-25  
**Branche** : `cursor/agent-runtime-audit-a2fe`  
**Périmètre** : lecture seule du code IchiVol + clones `trycompai/crm` (`apps/agent`) et `vercel/eve`.  
**Livrable** : ce fichier uniquement. Aucune modification runtime.

---

## 1. Architecture actuelle IchiVol

Séparation déjà réelle (à conserver) :

| Couche | Rôle aujourd’hui | Emplacements |
|---|---|---|
| **ENGINE** | Vérité mathématique : indicateurs, pipeline, screener, paper, risk | `ichivol-app/engine/` |
| **AGENT (LLM)** | Raisonnement / explication / outils lecture + confirmations humaines | `ichivol-app/server/src/agent/` |
| **BROKER** | Paper only (pas d’adaptateur OANDA/IBKR/Binance live) | `engine/app/paper/` |
| **FRONT** | Copilot chat + page Agents descriptive | `src/pages/AgentPage.tsx`, `AgentsPage.tsx` |

### 1.1 Indicateurs réellement présents (`engine/app/indicators/`)

Source de vérité : fichiers + `registry.py`. **Pas** la liste métier du brief.

| Module | ID registry | Statut registry | Calcule |
|---|---|---|---|
| `ichimoku.py` | `ichimoku` | PRODUCTION | Tenkan/Kijun/Senkou, projected kumo |
| `rvol.py` | `rvol` | PRODUCTION | Relative volume / anomalies |
| `atr.py` | `atr` | PRODUCTION | ATR + régime volatilité |
| `adx.py` | `adx` | PRODUCTION | ADX / DI |
| `rsi.py` | `rsi` | CANDIDATE | RSI |
| `cmf.py` | `cmf` | CANDIDATE | Chaikin Money Flow |
| `obv.py` | `obv` | CANDIDATE | OBV |
| `cvd.py` | `cvd` | PRODUCTION | CVD |
| `donchian.py` | `donchian` | PRODUCTION | Donchian |
| `structure.py` | `structure` | PRODUCTION | Market structure (swings) |
| `location.py` | `location` | PRODUCTION | Location prix/nuage + **VP / VWAP / AVWAP** (pas d’ID `vwap` séparé) |
| `impulse.py` | `impulse` | EXPERIMENTAL | Impulsion |
| `fvg.py` | `fvg` | EXPERIMENTAL | Fair Value Gaps |
| `ichimoku_analytics.py` | `ichimoku_analytics` | EXPERIMENTAL | Analytics Ichimoku (deps ichimoku, atr) |
| `ppo.py` | `ppo` | REJECTED | PPO (Lab) |
| `best_cloud.py` | `best_cloud` | REJECTED | Best cloud |
| `wyckoff.py` | `wyckoff` | REJECTED | Wyckoff (deps donchian) |
| `pivots.py` | — | **hors registry** | Helper pivots causaux |
| `oi_funding.py` | — | **hors registry** (volontaire) | OI / funding futures |

**Corrections vs brief** : VWAP n’est pas un indicateur standalone ; PPO/FVG existent ; OBV/CMF/RSI sont CANDIDATE ; pas de module « multi-timeframe » dédié (comparaison TF = commandes agent / screener).

### 1.2 Agents déterministes (pas LLM)

`engine/app/agents/` : `ichimoku_agent.py`, `rvol_agent.py`, `types.py` (`StrategyAgentOutput`). Pure compute via `REGISTRY.compute`. **Aucun LLM.**

### 1.3 Agent channel engine (allowlist, zéro LLM)

`engine/app/agent_channel/` — contrat `{cmd, args}` → `{ok, data|error}`.

- Lecture : screener, décisions, structure, news, calendar, lab, indicateurs, chart objects read…
- Écriture **uniquement** overlays chart (`draw_*`, `delete_chart_object`) — source forcée `claude`.
- **Jamais** d’ouverture/fermeture de position paper sur ce canal (doc + code confirmés).

### 1.4 Copilot serveur (Claude)

`server/src/agent/` :

- `claudeAgent.ts` — boucle outils Anthropic ; outils engine via `engineAgentChannel.ts`.
- Outils locaux historiques : `getLiveSnapshot`, `getDecisionDetail`, `getJournalContext`, `searchKb`.
- `planner.ts` — intents allowlist ; mute confirmés : `save_decision`, `pin_symbol`, `open_paper_position`.
- Persistance : Prisma `agent_threads` / `agent_messages` / `agent_actions`.
- `actionsRoute.ts` — confirmation humaine ; paper open = `POST /paper/positions` (engine re-décide ; le LLM ne vote pas la direction).

### 1.5 Risk + paper

- `risk_kernel.py` : `evaluate(...)` — kill switch, daily loss, stale, max positions, open risk, symbol exposure, sizing…
- `kill_switch.py` : `entries_blocked = kill_switch_armed OR daily_loss_locked`.
- `PaperOrder` : journal de fills paper (BUY/SELL MARKET), **pas** une machine d’état d’ordre live multi-broker.
- Boucles fond (`main.py` lifespan) : screener-cache, protection-monitor, signal-outcomes, backtest-evidence — **threads daemon in-process**, données DB persistées, **runners non durables** (pas de table de tâches).

### 1.6 Front Agents

`AgentsPage.tsx` : 6 rôles maquette **NON CONNECTÉ** + chaîne d’autorité éditoriale. Seul signal live : `useLlmStatus()`. Aucune mission / file / recheck.

### 1.7 Ce qui n’existe pas (confirmé)

Pas de table `agentTask`, pas de `schedule_recheck`, pas de leases `FOR UPDATE SKIP LOCKED`, pas de Redis/Celery, pas de bus d’événements agent, pas de wake conditionnel sans LLM, pas de multi-agent runtime.

---

## 2. Architecture réelle Comp AI / Eve

### 2.1 Eve (Vercel) — runtime TypeScript, conventions

D’après le code/docs du clone `vercel/eve` :

- Harness : tours LLM, compaction, tools, skills, channels, schedules, sandbox, memory.
- Layout `agent/` : `tools/`, `skills/`, `schedules/`, `channels/`, `subagents/`, `memory/`.
- Skills : fichiers `.md` / modules découverts par path → chargés **à la demande** (`load_skill`), pas un monolithe system prompt.
- Schedules Eve : fichiers `defineSchedule({ cron })` **statiques** au build. La doc `patterns/dynamic-scheduling.md` dit explicitement : pour du scheduling dynamique, **mettre les rows dans le store applicatif** + un cron minute qui claim + `receive(...)`.
- Eve **ne fournit pas** la file durable métier : il fournit le runtime de session et les hooks cron.

### 2.2 Comp AI CRM (`apps/agent`) — autonomie = leur file Postgres

Constat Claude **confirmé** dans le code :

| Pièce | Fichier | Comportement |
|---|---|---|
| Table tâches | Prisma `AgentTask` (`agentTask`) | `dueAt`, `priority`, `budget`, `attempts`, `leasedUntil`, `reason`, `payload`, `finishedAt`, `outcome` |
| Claim atomique | `lib/tasks.ts` `claimDue` | `FOR UPDATE SKIP LOCKED`, incrément `attempts`, pose lease |
| Recheck outil | `tools/schedule_recheck.ts` | `defineTool` Eve ; **reason obligatoire** (≥10 car.) ; écrit `kind: "recheck"` via `scheduleTask` |
| Dispatcher | `schedules/dispatch.ts` | `cron: "* * * * *"` → `reconcileStaleTasks` + `drainAll` + runs custom |
| Stale | `lib/stale-tasks.ts` | Ferme / retire / libère tâches coincées |
| Config | `lib/dispatch-config.ts` | Batches, leases (6–30 min), max attempts, timeouts |

Eve = conventions + cron + session. **Comp AI = owner de la queue durable.**

---

## 3. Ce qui est transposable

1. **Table de tâches Postgres + claim SKIP LOCKED** (cœur de l’autonomie Comp AI).
2. **Outil `schedule_recheck` avec raison obligatoire** + budget + dueAt.
3. **Cron / worker minute** qui drain les tâches échues (pas une boucle LLM permanente).
4. **Réconciliation stale** (leases expirés, attempts max → retire).
5. **Tools comme façade** : l’agent n’écrit pas la DB métier ni les clés broker ; il appelle des tools typés.
6. **Skills on-demand** (patterns Eve) pour Ichimoku/RVOL/structure/risk au lieu d’un prompt géant.
7. **Séparation ENGINE / AGENT / BROKER** déjà alignée avec le modèle Comp/Eve tools→backend.
8. **Human-in-the-loop** pour actions mutantes (déjà dans IchiVol planner/actions).

---

## 4. Ce qui ne doit pas être transposé

| Élément Comp/Eve | Pourquoi pas |
|---|---|
| Domaine CRM (contacts, deals, enrichment, Slack people) | Hors produit trading |
| Sandbox bash / write_file générique | Surface d’attaque inutile ; IchiVol a déjà un allowlist engine |
| Multi-tenant Eve / channels Slack comme cœur | IchiVol = app web + moteur Python |
| Subagents builder qui génèrent du code agent | Complexité CRM ; pas le besoin immédiat |
| Intégration Eve complète comme runtime principal | Duplique Node+Python ; coût ops ; Python garde la vérité marché |
| Boucle LLM sur chaque candle pour 30 symboles | Coût et latence ; viole l’exigence événementielle |
| 6 « agents » permanents front mappés 1:1 runtime | Maquette descriptive ≠ justification multi-process |

---

## 5. Gaps dans IchiVol

| Capacité cible (exemple BTC) | État |
|---|---|
| Mission persistante « surveiller BTCUSDT » | Absente |
| Verdict NO TRADE + conditions RVOL/ADX | Pipeline/screener partiel ; pas d’objet « watch until condition » |
| `schedule_recheck(next_closed_candle)` | Absent |
| Évaluation condition **sans** LLM | Absent (threads protection ≠ missions agent) |
| File multi-symboles + crash recovery | Absente |
| Kill-switch **agents** (distinct paper) | Absent (kill paper existe) |
| Budget LLM / jour / tâche | Absent |
| UI contrôle Agents live | Placeholder |

**Réutilisable tel quel** : indicateurs (dont ADX/RVOL/structure), décisions/screener, agent_channel, Copilot tools, risk_kernel, kill_switch paper, paper positions, threads/actions, watchlist, news/calendar engine.

---

## 6. Eve vs architecture native IchiVol

| Critère | A. Intégrer Eve | B. Principes Eve en Python | C. Infra IchiVol seule | D. Hybride (recommandé) |
|---|---|---|---|---|
| Complexité | Haute (nouveau runtime TS) | Moyenne | Faible court terme / plafond bas | Moyenne maîtrisée |
| Robustesse file | Dépend d’un store custom + Eve cron | Native Postgres dans engine/server | Threads non durables | Postgres tasks + worker |
| Maintenance | Deux stacks agents | Une stack Python | Peu de nouveau code | Server Node pour LLM + engine pour eval |
| Coût LLM | Facile de mal faire (wake trop souvent) | Contrôlable si eval engine d’abord | Pas d’autonomie | Eval engine → LLM rare |
| Latence | Session Eve + proxy engine | Direct | Direct | Direct tools existants |
| Observabilité | Eve telemetry + custom | À bâtir | Logs existent | Audit table + logs |
| Scalabilité | Workers Eve | Workers Python | 1 process | Claim SKIP LOCKED |
| Sécurité | Sandbox Eve + tools | Allowlist Python | Allowlist actuel | Étendre agent_channel + risk |
| Fit Python | Mauvais (double vérité) | Excellent | Excellent | Excellent |

**Verdict** : **D hybride** — ne pas adopter Eve comme runtime IchiVol ; **copier les principes Comp AI** (tasks Postgres, leases, recheck, stale) dans le stack existant ; garder Claude côté `server/src/agent` ; garder le calcul côté `engine`.

---

## 7. Architecture cible recommandée (minimale)

```text
                    ┌─────────────────────────────┐
                    │   UI Agents (contrôle)      │
                    │   missions / file / budgets │
                    └─────────────┬───────────────┘
                                  │ HTTP
                    ┌─────────────▼───────────────┐
                    │  SERVER agent runtime       │
                    │  Claude + tools + confirm   │
                    │  (existant, étendu)         │
                    └──────┬─────────────┬────────┘
                           │             │
              schedule_*   │             │ tool calls
                           ▼             ▼
              ┌────────────────┐   ┌────────────────────┐
              │ agent_tasks DB │   │ ENGINE agent_channel│
              │ dueAt, lease,  │   │ + evaluate_watch    │
              │ condition JSON │   │ (déterministe)      │
              └───────┬────────┘   └─────────┬──────────┘
                      │ cron/worker          │
                      ▼                      ▼
              ┌────────────────┐   ┌────────────────────┐
              │ Dispatcher     │   │ INDICATORS / PIPE  │
              │ claimDue →     │   │ RISK KERNEL        │
              │  if condition  │   │ PAPER GATEWAY      │
              │  unmet: sleep  │   └────────────────────┘
              │  if met/expire │
              │  → wake Claude │
              └────────────────┘
```

**Boucle cible** : OBSERVE (engine) → ANALYZE (LLM si besoin) → DECIDE → ACT (tools / intent) → SCHEDULE NEXT (task row) → WAIT (pas de LLM) → DISPATCH → evaluate_condition (engine) → wake LLM seulement si met / expire / jugement.

---

## 8–20. Blocs d’implémentation (tableaux)

### 8. Agent runtime

| | |
|---|---|
| **Fichier existant** | `server/src/agent/claudeAgent.ts`, `planner.ts`, `threads.ts` |
| **Nouveau** | `server/src/agent/runtime/missionRunner.ts` (orchestre une tâche claimée) |
| **Rôle** | Exécuter un tour Claude borné (budget) pour une mission/tâche |
| **Depends on** | task repo, tool registry, system prompt/skills |
| **Does not** | Calculer indicateurs ; bypass risk ; boucle infinie |
| **Risques** | Double wake, prompt drift |
| **Tests** | Unit : budget respecté ; intégration : 1 tâche → 1 tour max |

### 9. Task queue

| | |
|---|---|
| **Fichier existant** | — (rien d’équivalent) ; Prisma server déjà là |
| **Nouveau** | Prisma `AgentTask` + `server/src/agent/tasks.ts` (claim/complete/schedule) **ou** table engine SQLAlchemy miroir — **préférence : Prisma server** (proche threads/actions) |
| **Rôle** | Persistance dueAt / lease / attempts / reason / payload / condition |
| **Depends on** | Postgres |
| **Does not** | Appeler le LLM |
| **Risques** | Contention multi-worker (mitigé SKIP LOCKED) |
| **Tests** | claim concurrent ; retry ; retire exhausted |

### 10. Event bus

| | |
|---|---|
| **Existant** | Threads protection / screener ; notifications server |
| **Nouveau (phase tardive)** | `engine/app/events/bus.py` léger (outbox table) — **pas** Redis obligatoire |
| **Rôle** | Publier `candle_closed`, `news_high_impact`, `position_event` → enqueue task |
| **Depends on** | market data / paper |
| **Does not** | Remplacer la task queue |
| **Risques** | Sur-engineering early |
| **Tests** | candle_closed → 1 task |

**Phase 1** : se passer d’un bus — le dispatcher + `evaluate_watch` sur dueAt / next bar suffit.

### 11. Tools

| | |
|---|---|
| **Existant** | `agent_channel` + tools server |
| **Nouveau** | Étendre channel : `evaluate_watch_condition`, `schedule_recheck` (écrit task via API server ou table partagée), `create_order_intent` (pas fill) |
| **Rôle** | Façade Eve-like : agent → tools → IchiVol |
| **Depends on** | registry allowlist |
| **Does not** | Accès SQL brut / clés broker |
| **Risques** | Surface d’écriture trop large |
| **Tests** | golden route_order ; read_only flags |

Mapping souhaité → existant :

| Outil cible | Déjà proche |
|---|---|
| get_market_snapshot / decision | `detect_signal`, `get_symbol_context`, getDecisionDetail |
| get_multi_tf | `compare_timeframes` |
| get_market_structure / levels | `get_structure`, chart objects |
| get_news / calendar | `get_news`, `get_calendar` |
| get_portfolio / positions | paper overview API (à exposer en tool) |
| schedule_recheck | **à créer** |
| create_order_intent / paper_* | confirmation humaine + paper engine |

### 12. Skills

| | |
|---|---|
| **Existant** | `systemPrompt.ts` monolithique (~115 lignes) + KB search |
| **Nouveau** | `server/src/agent/skills/*.md` (ichimoku, rvol, structure, risk, mtf…) chargés par nom de mission |
| **Rôle** | Contexte procédural on-demand (principe Eve) |
| **Depends on** | runtime prompt composer |
| **Does not** | Contenir des chiffres live |
| **Risques** | Skills obsolètes vs pipeline |
| **Tests** | skill X injectée seulement si mission type X |

### 13. Memory

| | |
|---|---|
| **Existant** | Threads messages ; journal décisions user |
| **Nouveau** | Champs mission : last_verdict, last_conditions, last_symbols_touched ; optionnel summary compact |
| **Rôle** | Continuité sans rejouer tout l’historique |
| **Does not** | Remplacer equity/paper DB |
| **Risques** | Hallucination si memory non ancrée engine |
| **Tests** | restart process → mission reprise |

### 14. Scheduler / Recheck

| | |
|---|---|
| **Existant** | Cron-like threads engine (non agent) |
| **Nouveau** | Worker minute (`server` ou `engine`) : reconcile + claimDue ; payload condition DSL |
| **Rôle** | Sleep sans LLM ; wake conditionnel |
| **Depends on** | tasks + `evaluate_watch_condition` |
| **Does not** | Appeler Claude si condition fausse et non expirée |
| **Risques** | Conditions mal formées |
| **Tests** | RVOL&ADX unmet → no LLM ; met → 1 wake |

#### Coût LLM estimé — 30 actifs

Hypothèses : modèle class Copilot (~$3–15 / MTok input selon provider) ; ~4k tokens/tour (prompt+tools) ≈ **$0.02–0.08 / wake** (ordre de grandeur, calibrer sur factures réelles).

| Mode | Wakes / jour (30 symboles) | Coût indicatif / jour |
|---|---|---|
| **Sans** gate déterministe (recheck LLM chaque 1H) | 30 × 24 = **720** | **~$15–60** |
| **Avec** condition engine (wake seulement si RVOL/ADX ok, expire, ou 1 digest / symbole / jour) | ~30–90 | **~$0.6–7** |

Facteur **×10–50** d’économie : le gate déterministe est **non négociable**.

### 15. Risk engine

| | |
|---|---|
| **Existant** | `risk_kernel.py`, kill_switch, daily loss lock |
| **Nouveau** | Point unique `ExecutionGateway.submit(intent)` → toujours `risk_kernel.evaluate` avant paper |
| **Rôle** | Autorité finale ; LLM ne peut pas contourner |
| **Depends on** | portfolio state, market freshness |
| **Does not** | « Expliquer » à la place de refuser |
| **Risques** | Outil paper_* qui bypass gateway |
| **Tests** | Claude BUY + daily_loss_locked → REFUSED, aucun PaperOrder |

### 16. Execution gateway

| | |
|---|---|
| **Existant** | `paper/engine.py` open/close |
| **Nouveau** | Interface `BrokerAdapter` ; impl `PaperAdapter` d’abord |
| **Rôle** | Order Intent → Risk → Adapter |
| **Does not** | Décider du signal |
| **Risques** | Fuite d’API broker dans tools LLM |
| **Tests** | Intent refusé n’atteint pas adapter |

### 17. Paper → real broker

**PaperOrder aujourd’hui** : enregistre fills paper (qty, prix, fees, status FILLED typique) liés au cycle open/close — **pas** : états NEW/PARTIAL/REJECTED live, routing multi-venue, auth OANDA/IBKR.

| Phase | Contenu |
|---|---|
| Now | PaperAdapter only |
| Later | Même intent + risk ; adapter réel derrière flag ; paper reste default |

Ne rien construire de jetable : intents et risk stables ; adapters minces.

### 18. Frontend Agents

| Donnée UI | Source backend à créer/exposer |
|---|---|
| État WORKING/WAITING/MONITORING | `AgentMission.status` + lease |
| Mission / symbole / raison d’attente | task.reason + payload |
| Prochain check | task.dueAt |
| File rechecks / candidats | list tasks open |
| Budget risque restant | overview.risk + mission budget LLM |
| Arrêt global agents | `agent_runtime_paused` flag (+ UI) |

Endpoints indicatifs (à designer, **pas implémentés ici**) :  
`GET /api/agent/missions`, `GET /api/agent/tasks`, `POST /api/agent/missions`, `POST /api/agent/runtime/pause`, `GET /api/agent/runtime/audit`.

### 19. Observabilité / audit

| | |
|---|---|
| **Nouveau** | Table `agent_run_audit` : task_id, tokens, tools[], verdict, wake_reason (`condition_met`\|`expired`\|`manual`\|`dispatch`) |
| **Rôle** | Traçabilité + coût |
| **Tests** | Chaque wake produit 1 ligne |

### 20. Sécurité / garde-fous

| Garde-fou | Mécanisme |
|---|---|
| Budget LLM / tâche / jour | Compteurs sur tasks + settings |
| Max rechecks / symbole | Contrainte unique open task / symbol+kind (comme Comp upsert) |
| Expiration mission | `expires_at` obligatoire |
| Kill-switch agents | Flag runtime + refuse claimDue |
| Allowlist tools | agent_channel + mute intents |
| Risk final | gateway |

---

## 21. Plan par phases (adapté au repo)

| Phase | Objectif | Livrables principaux |
|---|---|---|
| **P0** | Runtime minimal | Table tasks + claimDue + worker minute + audit log |
| **P1** | Tools + schedule_recheck | Outil recheck + raisons ; missions 1 symbole |
| **P2** | Recheck conditionnel | `evaluate_watch_condition` engine (RVOL/ADX/pipeline) ; wake LLM gate |
| **P3** | Scout autonome lecture | Mission multi-symboles (watchlist) ; digest ; **pas** d’ordres auto |
| **P4** | Risk gate + paper intent | Order intent → risk_kernel → paper only + confirm humaine optionnelle |
| **P5** | UI Agents contrôle | Brancher AgentsPage sur APIs réelles |
| **P6** | Multi-agent ? | Uniquement si métriques P3 prouvent besoin (voir § final multi-agent) |
| **P7** | Broker readiness | Interface adapter ; pas de go-live sans audit risk |

---

## Formats « fichier » pour les ajouts clés

```text
server/prisma/... AgentTask
ROLE : file durable missions/rechecks (modèle Comp AI)
DEPENDS ON : Postgres
DOES NOT : exécuter le LLM ni calculer indicateurs
TESTS : claim concurrent SKIP LOCKED ; retire exhausted
```

```text
server/src/agent/tasks.ts
ROLE : scheduleTask / claimDue / completeTask / reconcileStale
DEPENDS ON : Prisma AgentTask
DOES NOT : appeler Claude
TESTS : upsert recheck même symbole ; lease expiry
```

```text
server/src/agent/runtime/dispatcher.ts
ROLE : cron/worker minute — stale + drain due tasks
DEPENDS ON : tasks.ts, missionRunner, evaluate_watch (engine)
DOES NOT : boucle LLM permanente
TESTS : condition unmet → 0 wake ; met → 1 wake
```

```text
engine/app/agent_channel/commands.py (+ registry)
ROLE : evaluate_watch_condition ; évent. get_portfolio snapshot tool
DEPENDS ON : indicators registry, pipeline, paper read APIs
DOES NOT : ouvrir des positions ; appeler LLM
TESTS : fixture RVOL 0.82 ADX 18 → unmet ; seuils → met
```

```text
server/src/agent/tools/schedule_recheck.ts (ou cmd engine+API)
ROLE : écrire tâche dueAt + reason + condition optionnelle
DEPENDS ON : tasks.ts
DOES NOT : sleep in-process
TESTS : reason < 10 rejetée ; dueAt futur
```

```text
server/src/agent/skills/*.md
ROLE : procédures métier chargées selon mission
DEPENDS ON : prompt composer
DOES NOT : données marché live
TESTS : taille prompt bornée
```

```text
engine/app/paper/execution_gateway.py
ROLE : OrderIntent → risk_kernel → PaperAdapter
DEPENDS ON : risk_kernel, paper engine
DOES NOT : laisser le LLM filler un ordre
TESTS : daily_loss_locked → no PaperOrder
```

---

## Multi-agents : est-ce justifié ?

| Option | Verdict IchiVol |
|---|---|
| **1 agent + sous-tâches** (recommandé P0–P5) | Suffit : une mission = N tasks symboles ; tools + risk gateway |
| Agent + subagents Eve-like | Utile plus tard pour research long / sandbox — pas pour surveillance candle |
| Chef + Scout + Analyst + Risk permanents | **Non** au départ : Risk est déjà `risk_kernel` (code) ; Scout = screener existant ; « Chef » = dispatcher. Dupliquer en LLM multi-agents ajoute coût et races sans gain de sécurité |

La page 6 rôles reste une **vue organisationnelle** ; le runtime peut exposer des *lanes* (observe / decide / execute) sans 6 processus LLM.

---

## Question finale — architecture minimale

En partant du code **actuel** :

1. **Garder** engine (indicateurs + pipeline + risk + paper) et Copilot server (Claude + allowlist + confirm).
2. **Ajouter** une **file Postgres type Comp AI** (`AgentTask` + claim SKIP LOCKED + stale + cron minute) — c’est le seul greffon indispensable pour « dormir / se réveiller / survivre au restart ».
3. **Ajouter** `schedule_recheck` + **évaluation de condition dans l’engine** pour ne réveiller Claude que si nécessaire.
4. **Étendre** les tools existants (portfolio read, order intent) sans donner la DB ni le broker au LLM.
5. **Skills** markdown légers (principe Eve) — optionnel mais cheap.
6. **Ne pas** intégrer Eve comme runtime ; **ne pas** créer 6 agents LLM ; **ne pas** boucler Claude sur chaque candle.

Cela transforme le système « Utilisateur → Claude → réponse » en agent de surveillance **événementiel et persistant**, sans usine à gaz.

---

## Fichiers IchiVol à modifier / créer (si validation)

### Créer

- `docs/AGENT-RUNTIME-AUDIT.md` *(ce document)*
- `ichivol-app/server/prisma/schema.prisma` — modèles `AgentTask`, `AgentMission?`, `AgentRunAudit`
- `ichivol-app/server/src/agent/tasks.ts`
- `ichivol-app/server/src/agent/staleTasks.ts`
- `ichivol-app/server/src/agent/runtime/dispatcher.ts`
- `ichivol-app/server/src/agent/runtime/missionRunner.ts`
- `ichivol-app/server/src/agent/tools/scheduleRecheck.ts` (ou équivalent)
- `ichivol-app/server/src/agent/skills/*.md`
- `ichivol-app/engine/app/agent_channel/` — handler `evaluate_watch_condition`
- `ichivol-app/engine/app/paper/execution_gateway.py` (mince)
- `ichivol-app/server/src/routes/agentMissions.ts` (API contrôle UI)
- Tests : `server/.../tasks*.test.ts`, `engine/tests/.../test_evaluate_watch.py`

### Modifier

- `ichivol-app/engine/app/agent_channel/registry.py` — enregistrer nouvelles cmds read_only
- `ichivol-app/server/src/agent/claudeTools.ts` / `claudeAgent.ts` — tools recheck + budgets
- `ichivol-app/server/src/agent/systemPrompt.ts` — composer skills
- `ichivol-app/server/src/index.ts` (ou job runner) — démarrer dispatcher
- `ichivol-app/src/pages/AgentsPage.tsx` — **plus tard** (phase UI), pas dans le runtime core
- Settings : budgets LLM / pause runtime

### Ne pas toucher (pour cette trajectoire)

- Formules indicateurs / pipeline décisionnel métier
- Logique `risk_kernel` (seulement l’appeler plus systématiquement)
- Eve comme dépendance runtime
- CRM Comp AI (référence conceptuelle uniquement)

---

## Sources code consultées

- IchiVol : `engine/app/indicators/*`, `agents/*`, `agent_channel/*`, `paper/risk_kernel.py`, `paper/kill_switch.py`, `main.py` lifespan, `server/src/agent/*`, `src/pages/AgentsPage.tsx`
- Comp AI : `apps/agent/agent/lib/tasks.ts`, `stale-tasks.ts`, `dispatch.ts`, `dispatch-config.ts`, `schedules/dispatch.ts`, `tools/schedule_recheck.ts`, Prisma `AgentTask`
- Eve : docs agent-files, default-harness, patterns/dynamic-scheduling ; packages `eve` schedules/skills runtime

---

## Décisions validées (Claude, 2026-09-25)

Amendements retenus après relecture Claude. Ces points fixent le cadre avant toute implémentation runtime (phases P0→P2) — **après** clôture UI-P4.

### Option D hybride

- **Pas d’Eve en runtime** (référence conceptuelle uniquement).
- File **`AgentTask` Postgres** de type Comp AI, côté **server**.
- Claude reste dans `server/src/agent`.
- Conditions évaluées par l’**engine**.
- **`risk_kernel`** = autorité finale via **`execution_gateway`**.

### Idempotence

Chaque tâche porte une **clé d’idempotence**. Un retry après crash **ne peut pas** recréer une order intent, une mission ou un recheck déjà créés par la même tentative.

### Fraîcheur des données

`evaluate_watch_condition` vérifie **`data_quality`** (`stale` / `data_late`) :

- données périmées → **pas de réveil LLM** ;
- tâche **reprogrammée** ;
- raison **journalisée**.

### Clôture de bougie

Trigger `next_closed_candle` : `dueAt` fixé à la **clôture + 60 s** ; évaluation sur **bougies fermées uniquement**.

### Ordres paper

- **Confirmation humaine activée par défaut**.
- Ouverture automatique = réglage **explicite**, **désactivé**, activable plus tard.

### Mono-agent

**Mono-agent + sous-tâches** jusqu’à preuve du contraire. **Pas** de multi-agents LLM.

### Ordre de travail (gelé)

1. UI-P2 / UI-P3 — corrections, merge, VPS *(fait)*.
2. UI-P4 — PR **draft**, merge seulement après relecture Claude.
3. Runtime agents — phases **P0 → P2** de cet audit, **une PR draft par phase** (file + dispatcher + audit log ; `schedule_recheck` ; recheck conditionnel engine). **Ne pas démarrer** tant que P4 n’est pas validée.
