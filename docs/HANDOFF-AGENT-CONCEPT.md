# Handoff Claude — Concept agents IchiVol (rectifier trajectoire)

> **Pour :** Claude (engine Python / auth-DB / toute session qui touche aux « agents »)  
> **De :** Cursor + décision produit utilisateur (2026-09-15)  
> **Priorité :** si tu reprends une session **déjà en cours** → d’abord [`HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md`](./HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md)  
> **Docs parentes :** [`TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md) · [`METHODS-ROADMAP.md`](./METHODS-ROADMAP.md) · [`APP-ARBORESCENCE-V2.md`](./APP-ARBORESCENCE-V2.md) · [`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md) · [`GROKDESK_REUSABLE_COMPONENTS.md`](./GROKDESK_REUSABLE_COMPONENTS.md) · [`AUDIT-AJOUTS-AUTH-DB-AGENT.md`](./AUDIT-AJOUTS-AUTH-DB-AGENT.md) · [`INTEGRATION_PLAN.md`](./INTEGRATION_PLAN.md)

---

## 0. Si tu n’as pas encore commencé ce sujet

**Garde le cap ci-dessous.** Ne démarre pas :

- un bureau multi-personas LLM (style GrokDesk « 19 agents »)
- un chat libre sans tools
- la fusion du copilot LLM avec les StrategyAgents Python

Si tu as déjà commencé dans une de ces directions : **stop**, aligne sur ce doc, ne merge pas du code « desks / firing / rewrite prompt ».

---

## 1. Décision produit (figée)

IchiVol = **deux couches séparées**. Elles coexistent ; elles ne se mélangent pas.

| Couche | Rôle | Techno | LLM ? |
|--------|------|--------|-------|
| **A. StrategyAgents** | Analyser le marché, sortir une décision structurée | Python `engine/app/agents/` | **Non** (déterministe / indicateurs) |
| **B. Copilot** | Expliquer, citer la KB, proposer des actions confirmées | TS `server/src/agent/` + chat UI | **Oui** (clé Settings) |

**North star verrouillée :** [`TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md)  
**Pages V2 + rôles LLM :** [`APP-ARBORESCENCE-V2.md`](./APP-ARBORESCENCE-V2.md)

Phrase fondatrice :

> Ichimoku trouve la direction, RVOL exige la participation, ATR mesure le risque — les autres agents ne confirment ou n’invalident, jamais ne diluent le signal central.

```
MARKET → SCREENER → étages (Ichimoku → RVOL → Structure → ATR → score)
                         ↓
                  DECISION ENGINE
                  BUY|SELL|WATCH|NO_TRADE
                         ↓
              (V1.5–V2) Paper → Performance → Backtest
                         ↓
              UI Décisions (pipeline visible)

Consensus multi-agents = V2 **après** preuve backtest — pas avant.

En parallèle (hors pipeline de sizing) :
  User ⇄ Copilot chat (skills allowlist) — jamais de vote direction
```

---

## 2. Couche A — StrategyAgent (moteur)

### Concept
Chaque agent implémente le même contrat (déjà dans `engine/app/agents/types.py` et §3 de `TRADING_ARCHITECTURE_V2.md`) :

```text
StrategyAgentOutput {
  agent, direction (LONG|SHORT|NEUTRAL),
  probability, confidence, expected_value,
  reasons[], invalidation[], metadata
}
```

Puis un **pipeline à étages** (cible) agrège les sorties → une décision produit  
(`BUY|SELL|WATCH|NO_TRADE` — aujourd’hui encore `combiner.py` en produit de confidences = MVP à remplacer).

**Ne pas** traiter `confidence = ichimoku * rvol` comme la règle produit définitive.

### Déjà en place (ne pas refaire)
- `ichimoku_agent.py`, `rvol_agent.py`
- `combiner.py` (MVP)
- Routes engine (voir handoff frontend à jour) : screener / decisions

### Next engine (ordre — V1)
1. Remplacer le combiner × par un **decision pipeline** à portes (Direction → Participation → Structure/MTF → Régime/Risque → label)  
2. `structure_agent` (Price Action) + MTF, puis `volatility_agent` (ATR)  
3. V1.5 : Volume Profile + VWAP/AVWAP (location)  
4. Exposer les étages au front (`DecisionsPage`)  
5. V2 CVD/OI/Funding + Consensus = **seulement après backtest**

Voir [`METHODS-ROADMAP.md`](./METHODS-ROADMAP.md).

### Interdit couche A
- Appeler Anthropic/OpenAI/OpenRouter depuis un StrategyAgent « pour raisonner »
- Personas narrative / firing / rewrite de prompt GrokDesk
- Laisser RVOL ou ATR voter la **direction**
- Décider d’une taille de position dans l’agent Ichimoku/RVOL (ATR/Risk sizes, plus tard)

---

## 3. Couche B — Copilot (chat + skills)

### Concept
**Un seul chat.** Pas N agents conversationnels.

L’utilisateur parle ; le serveur sélectionne un **skill / tool allowlisté** :

| Skill (MVP → suite) | Fait |
|---------------------|------|
| `explain_signal` | Explique le signal live (chiffres = payload front / API, jamais inventés) |
| `research` | Répond via KB Academy + citations |
| `trade_idea` | Idée de marché + disclaimer |
| `save_decision` | (P4) Persiste une décision après confirm user |
| `pin_symbol` / `refresh_screener` | (P5) Actions cockpit confirmées |

Modes UI déjà là (`explain_signal` / `research` / `trade_idea`) = intention.  
Skills = capacités exécutables derrière.

### Déjà en place
- `POST /api/agent/chat` + RAG + providers LLM + Settings clés
- Anti-hallu chiffres marché

### Next copilot (auth/DB — P3/P4/P5 audit)
1. Threads / messages persistés  
2. Mémoire décisions dans le prompt  
3. Orchestrateur d’actions allowlist + `audit_log`  
4. **Pas** transformer le copilot en StrategyAgent

### Interdit couche B
- Laisser le LLM inventer OHLC / RVOL / biais  
- Ordres broker / retraits  
- Appels GSMS / CRM  
- Multi-agents LLM qui se votent entre eux pour le chat

---

## 4. Ce que disent les repos de référence (rappel)

| Repo / doc | À garder | À rejeter pour IchiVol |
|------------|----------|-------------------------|
| **GrokDesk** | Bus pub/sub, veto Risk absolu, calibration bornée (pattern) | Org chart 19 agents, firing, rewrite prompt, PnL synthétique |
| **Architecture V2** | Pipeline à étages, Structure+ATR avant Consensus | Usine multi-indicateurs, consensus trop tôt |
| **Audit Auth/DB** | Mémoire + actions allowlist sur le **copilot** | Fusion avec engine |
| **BacktestBot** | Plus tard : optimisation / backtest | Remplacer le chat ou les StrategyAgents maintenant |
| **Ichimoku ref** | Maths indicateur | Agents |

Matrice détaillée : `GROKDESK_REUSABLE_COMPONENTS.md` ligne « Agent chat = KEEP hors StrategyAgent ».

---

## 5. Règles non négociables

1. **StrategyAgent ≠ Copilot** — fichiers, APIs et UI séparés.  
2. **Chat + skills**, pas chat nu, pas multi-personas.  
3. **Chiffres marché** = données injectées / fetch ; jamais hallucinés.  
4. **Action → confirmation user** (sauf lecture seule).  
5. **IchiVol ≠ GSMS** — DB et scope trading only.  
6. Ne pas casser Settings / shell densifié Cursor.

---

## 6. Critères « trajectoire OK »

Tu es aligné si :

- [ ] Engine continue sur agents **structurés** + combiner (pas de LLM dans `engine/app/agents/`)  
- [ ] Copilot reste dans `server/src/agent/` avec skills allowlist  
- [ ] Front : `AgentChat` = copilot ; futur `ConsensusPanel` / `DecisionsPage` = sorties StrategyAgents  
- [ ] Aucun code « GROK CORE / firing / rewrite agent »  
- [ ] Doc / code mentionnent clairement les deux couches

Tu es **hors trajectoire** si tu ajoutes des personas LLM qui votent, ou si le chat décide seul d’un trade sans StrategyAgent + confirm.

---

## 7. Prompt collable pour Claude

```
Lis docs/HANDOFF-AGENT-CONCEPT.md en entier avant de coder quoi que ce soit sur les agents.

Rectifie ta trajectoire si besoin :
- Couche A = StrategyAgents déterministes (engine Python, contrat StrategyAgentOutput)
- Couche B = un seul Copilot chat + skills allowlist (server TS)
- Ne fusionne PAS les deux
- Ne porte PAS le multi-agents GrokDesk (desks/firing/rewrite)
- Next engine : brancher décisions au front / stabiliser combiner
- Next server : P3 threads + P4 mémoire décisions (audit)

Confirme en 5 lignes ce que tu vas faire / ne pas faire, puis exécute.
```

---

## 8. Fichiers à lire en premier

```
docs/HANDOFF-AGENT-CONCEPT.md          ← ce fichier
docs/TRADING_ARCHITECTURE_V2.md        §1–3, §2 (répartition Python/TS)
docs/GROKDESK_REUSABLE_COMPONENTS.md   ligne StrategyAgent + Agent chat
docs/AUDIT-AJOUTS-AUTH-DB-AGENT.md     §3 Agent IA
ichivol-app/engine/app/agents/types.py
ichivol-app/engine/app/decision/combiner.py
ichivol-app/server/src/agent/
```

---

*Handoff produit — source de vérité pour le concept agents. Si conflit avec une ancienne note « desks GrokDesk » ou « agents LLM qui tradent », ce document gagne.*
