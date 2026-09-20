# Handoff Claude — IchiVol V2 Validation Desk + Claude Trading Desk

> **Pour :** Claude Code (engine Python + éventuellement `server/src/agent/`)  
> **De :** Cursor + missions produit utilisateur (2026-09-20)  
> **Fichier maître** — remplace / étend l’ancien périmètre « AlgoPro seul »  
> **Companions :** [`ICHIVOL_V2_AUDIT.md`](./ICHIVOL_V2_AUDIT.md) · [`ICHIVOL_V2_ROADMAP.md`](./ICHIVOL_V2_ROADMAP.md)  
> **Lire aussi :** [`ARCHITECTURE-CONSOLIDEE-V2.md`](./ARCHITECTURE-CONSOLIDEE-V2.md) · [`EVIDENCE-ARCHITECTURE.md`](./EVIDENCE-ARCHITECTURE.md) · [`TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md) · [`HANDOFF-CURSOR-CLAUDE-AGENT-2026-09-20.md`](./HANDOFF-CURSOR-CLAUDE-AGENT-2026-09-20.md)

---

## 0. Règles absolues (figées)

| Règle | |
|-------|--|
| ❌ | Refaire IchiVol de zéro / 2ᵉ projet parallèle |
| ❌ | Casser le pipeline existant |
| ❌ | Installer Grok / API xAI / clone GrokBot |
| ❌ | Remplacer Claude par un autre système agentique |
| ❌ | LLM → BUY → broker |
| ❌ | Copier Pine TraderOracle / AlgoPro (source non officielle) |
| ❌ | Empiler JMA/SAR/MACD « parce que le script les a » |
| ✅ | CODE DU REPO = source de vérité |
| ✅ | Paper / shadow / mesure avant tout broker réel |
| ✅ | **Claude raisonne · Python calcule · DB mesure · Humain valide** |
| ✅ | Noyau **Ichimoku × RVOL** + Structure ; le reste = features / veto |
| ✅ | Décisions sur **bougies clôturées** ; prix live = UI / PnL / entry estimate |

**Objectif produit :**

```text
AI MARKET ANALYSIS + VALIDATION DESK
= observatoire quantitatif + décision + simulation + auto-évaluation
```

Boucle minimale à protéger / compléter :

```text
SIGNAL → DECISION → SHADOW/PAPER → OUTCOME → METRICS
```

---

## 1. Intégration Claude AUJOURD’HUI (vérifiée dans le code)

### Verdict en une phrase

> IchiVol utilise Claude via **HTTP `fetch` custom** vers l’API Messages Anthropic (tool-use + SSE) quand `provider === 'anthropic'` ; sinon OpenRouter/OpenAI en chat classique avec tools injectés côté serveur. **Pas** de `@anthropic-ai/sdk`, **pas** de Claude Agent SDK, **pas** de MCP runtime, **pas** de Grok, **pas** de ClaudeReviewer post-quant — uniquement le **Copilot / chat**.

### Classification → **CAS B** (SDK classique = fetch maison, tool calling Anthropic natif)

| Élément | Réalité repo |
|---------|----------------|
| Provider | `anthropic` \| `openai` \| `openrouter` |
| Package | **Aucun** SDK LLM dans `package.json` / `requirements.txt` |
| Init | `server/src/agent/claudeAgent.ts` + `claudeTools.ts` ; `providers/anthropic.ts` |
| Auth | `ANTHROPIC_API_KEY` / UI `llmKeysEnc` via `resolveLlmForUser` |
| Modèle | `LLM_MODEL` + override settings / body |
| Tools | Manifest engine `/agent/tools` (read-only) + `search_knowledge` ; max 6 tours |
| Orchestration | Planner regex → mute writes → LLM ; writes = confirm utilisateur |
| Persistence | Threads agent ; settings LLM |
| Endpoints | `POST /api/agent/chat`, `POST /api/agent/actions/confirm`, threads |
| Front | `AgentPanel.tsx`, `lib/agent.ts`, page `/app/agent` (Copilot) |
| Engine | `agent_channel/` — commandes lecture seule, **zéro LLM** |

### Architecture ACTUELLE

```text
[AgentPanel / Copilot]
        │  POST /api/agent/chat
        ▼
[Express route.ts] → planner (mute write intents)
        │
        ├── anthropic → runClaudeAgent
        │                 ├── GET engine /agent/tools
        │                 └── loop api.anthropic.com/v1/messages (+tools, SSE)
        │                       ├── search_knowledge
        │                       └── engine /agent/command
        │
        └── openai|openrouter → runReadOnlyToolsForMode
                                  → prompt + provider.chat()
```

### Architecture CIBLE (Claude Trading Desk — inspiration Grok **idées seulement**)

```text
MARKET DATA → DATA QUALITY → CLOSED CANDLES
        ↓
PYTHON QUANT ENGINE (Ichimoku×RVOL×Structure×…)
        ↓
TradeCandidate + Risk (déterministe)
        ↓
┌───────────────────────────────────────┐
│  CLAUDE ORCHESTRATOR (réutiliser     │
│  claudeAgent / tools — PAS 5 bots)   │
│  Reviewer → APPROVE|REJECT|CAUTION   │
│  (plus tard: Auditor / Researcher)   │
└───────────────────────────────────────┘
        ↓  structured ClaudeReview (Pydantic/Zod)
        ↓
quant_decision  +  claude_review  +  final_paper_action   (3 champs séparés)
        ↓
SHADOW / PAPER → OUTCOME (MFE/MAE) → PERFORMANCE DB → Strategy Lab
```

**Choix d’architecture recommandé : OPTION 1 / 4**

- 1 orchestrateur Claude (chemin Anthropic existant)
- + tools déterministes Python (étendre allowlist)
- + structured output validé
- **Pas** 5 instances Claude × 100 marchés (coût / latence)

GrokBot (`L1vsun/GrokBot-Trading-Desk__Setup-Prompt`) = **inspiration patterns** (rôles, journal, desk).  
**Grok n’entre pas dans IchiVol.**

---

## 2. Étude AlgoPro / TraderOracle (rappel)

Voir détail historique ci-dessous §A.  
Source : https://github.com/TraderOracle/TradingView (`AlgoPro Reverse.pine.txt`) — **non officiel** ; AlgoPro = scripts Invite-only TradingView.

**Retenir :** confluence ON/OFF + mesure.  
**Ignorer :** JMA, Range Filter, SAR, MAC-Z, dynamic leverage (défaut).

---

## 3. Synthèse audit repo → companions

Inventaire détaillé + classement EXISTE / PARTIEL / ABSENT / À CORRIGER / À RÉUTILISER :

→ **[`ICHIVOL_V2_AUDIT.md`](./ICHIVOL_V2_AUDIT.md)**

Tranches P0→P5 + première tranche concrète :

→ **[`ICHIVOL_V2_ROADMAP.md`](./ICHIVOL_V2_ROADMAP.md)**

### Points clés (ne pas greenfielder)

| Domaine | Statut |
|---------|--------|
| Strategy Lab Phases 1–8 | **EXISTE** `engine/app/strategy_lab/` |
| Evidence + OutcomeTracker (MFE/MAE, forward) | **EXISTE** `engine/app/evidence/` |
| Paper multi-portfolio + MFE/MAE | **EXISTE** |
| ShadowBroker counterfactual | **PARTIEL** / docs |
| Closed candles décisions | **EXISTE** `decide_on_closed_candles=True` + `closed_candles()` |
| DecisionSnapshot unifié nommé | **PARTIEL** (`SignalContext`) |
| strategy_version sur chaque décision | **PARTIEL** — à durcir |
| Confluence familles pondérées versionnées | **PARTIEL** |
| ClaudeReviewer post-quant + A/B | **ABSENT** |
| Structured `ClaudeReview` schema | **ABSENT** |
| Monte Carlo | **ABSENT** |
| UI « Strategy Lab » / « AI Trading Desk » | **PARTIEL** (Backtests / Copilot / Synthèse) |
| Live path = Lab path (même features) | **PARTIEL** — 3 stacks |

---

## 4. Première tranche à implémenter (après lecture audit/roadmap)

**Ne pas** commencer par 50 agents ni nouveaux indicateurs.

### Tranche T0 — Contrats mesurables (engine + types)

1. **`DecisionSnapshot`** DTO = sérialisation unique de `SignalContext` + stages + `strategy_version` + reason_codes.  
2. Persister / exposer sans table jumelle (champs evidence existants).  
3. Documenter mapping horizons Outcome ↔ clock (`1h` → T+1H = 1 barre).

### Tranche T1 — ClaudeReviewer minimal (server)

1. Réutiliser `claudeAgent` / tools ; **nouveau** mode ou endpoint dédié (pas un 2ᵉ Copilot).  
2. Input = TradeCandidate JSON **déjà calculé** par Python (tools `get_trade_candidate`, snapshot, risk…).  
3. Output = schema strict `ClaudeReview` (`APPROVE|REJECT|CAUTION` + factors).  
4. Invalide → **aucune** action paper.  
5. Stocker `quant_decision` / `claude_review` / `final_paper_action` séparément.  
6. A/B : paper A = quant seul ; paper B = après review (même signal).  
7. Tests : schema + refus JSON invalide + pas d’appel broker.

### Découpage binôme

| Qui | T0 / T1 |
|-----|---------|
| **Claude Code** | DecisionSnapshot engine, strategy_version, tools engine manquants, tests Python |
| **Cursor** | Schema Zod/TS `ClaudeReview`, route reviewer, branchement paper A/B, UI minimale « review » |

---

## 5. Ce qu’il ne faut PAS toucher

- Combiner / north star 5 questions (`TRADING_ARCHITECTURE_V2`)
- PaperBroker vs ShadowBroker glossaire
- Volume semantics (`volume_type`)
- Allowlist write tools (confirm utilisateur)
- Pipeline screener closed-candle path
- Refonte UI cosmétique / faux P&L

---

## 6. Message court pour Claude Code

> Tu n’ajoutes **pas** Grok. Tu **réutilises** le Copilot Anthropic (`claudeAgent` + tools engine).  
> Tu **n’ajoutes pas** JMA/SAR/MACD. Lab + Evidence existent — unifie DecisionSnapshot et branche un **ClaudeReviewer** après le quant, avec sorties structurées et A/B paper.  
> Mesure > démo. Première boucle : snapshot → decision → (review) → paper/shadow → outcome → metrics.

---

# Annexe A — AlgoPro Reverse (étude concepts)

Repo tiers : `TraderOracle/TradingView` · fichier `AlgoPro Reverse.pine.txt` · titre `AlgoPro V3 Reverse`.

**Non officiel.** Invite-only = distribution AlgoPro réelle.

Pattern observé : filtres `Act_*` chaînés puis AND → confluence configurable.

| Concept | IchiVol |
|---------|---------|
| Confluence ON/OFF | → ruleset / profiles (**réutiliser**) |
| Volume SMA×f | → **RVOL** déjà mieux |
| ADX / ATR | → déjà |
| JMA / RF / SAR / MAC-Z | → **ignorer** |
| Perf dashboard | → Lab + Paper + Activity |

---

# Annexe B — Structure / trendlines (inspiration, pas deps aveugles)

Repos à évaluer **avant** toute dépendance :

| Repo | Question |
|------|----------|
| mvpp/trend-line-detector | Déjà partiellement intégré côté Structure ? |
| GregoryMorse/trendln | Idem |
| ednunezg/pytrendline | Idem |

Pour chacun : licence, maintenance, tests, redondance vs adapters actuels, risque de complexifier.  
**Ne pas** ajouter une lib « parce qu’elle existe ».

Réponse attendue (dans un ticket / PR) : 9 points du prompt mission §33 — déjà amorcé dans Structure IchiVol ; comparer avant d’étendre.

---

# Annexe C — Glossaire anti-collision

| Terme | Sens |
|-------|------|
| Copilot / Agent chat | LLM conversationnel actuel |
| ClaudeReviewer | Rôle post-quant (**à créer**) — pas le chat libre |
| PaperBroker | Compte fictif capitalisé |
| ShadowBroker | Counterfactual (n’affecte pas cash) |
| Shadow mode | Enregistrer signal sans fill |
| Strategy Lab | `strategy_lab/` + UI Backtests |
| GrokBot | Inspiration externe **uniquement** |
