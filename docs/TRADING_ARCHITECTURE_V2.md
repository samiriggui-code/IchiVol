# IchiVol — Architecture verrouillée (north star)

**Statut : VERROUILLÉ** — décision produit 2026-09-15.  
Ce document **remplace** l’ancienne proposition « multi-strategy × consensus trop tôt ».  
Toute session engine / front / agents doit s’aligner ici avant d’ajouter une couche.

Docs liées :
- [`ARCHITECTURE-CONSOLIDEE-V2.md`](./ARCHITECTURE-CONSOLIDEE-V2.md) — lab quant (Paper / Shadow / Market Structure / MCP viz)
- [`PLAN-PAPER-BROKER-MULTI-PORTFOLIO.md`](./PLAN-PAPER-BROKER-MULTI-PORTFOLIO.md) — Phase 1 PaperBroker
- [`CAHIER-DES-CHARGES.md`](./CAHIER-DES-CHARGES.md) — backlog maître (dont Graph/Matrix réinterprété)
- [`METHODS-ROADMAP.md`](./METHODS-ROADMAP.md) — méthodes, 5 questions, V1→V3
- [`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md) — data gratuite ≠ execution
- [`APP-ARBORESCENCE-V2.md`](./APP-ARBORESCENCE-V2.md) — pages + LLM
- [`HANDOFF-AGENT-CONCEPT.md`](./HANDOFF-AGENT-CONCEPT.md)

---

## 0. Phrases fondatrices

> **Ichimoku trouve la direction, RVOL exige la participation, la location dit si l’emplacement est bon, ATR mesure le régime/risque — le reste confirme ou invalide, jamais ne dilue en salade de votes.**

> **Binance Vision nourrit le cerveau ; IchiVol décide ; le lieu où tu trades reste ouvert (paper d’abord).**

IchiVol n’est **pas** une usine à indicateurs (RSI + MACD + Stoch + … → N votes LONG).  
IchiVol n’est **pas** une plateforme de trading Binance : le feed [Market Data Only](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md) = OHLCV public uniquement.

---

## 1. Cinq questions (pas trois votes)

```
Direction → Participation → Location → Régime → Risque → DÉCISION
```

```
                         ICHIVOL
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
    STRUCTURE          PARTICIPATION          RÉGIME
    Ichimoku + PA          RVOL (+CVD V2)      ATR (+…)
    + MTF                  (+OI/Funding V2)
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                      MARKET LOCATION
                   VP · VWAP/AVWAP · S/R
                            ▼
                     SETUP QUALITY → BUY | WATCH | NO TRADE
```

| Question | Couche | CORE aujourd’hui | Droit | Interdit |
|----------|--------|------------------|-------|----------|
| **Direction** | Structure | Ichimoku | LONG / SHORT / NEUTRAL | — |
| **Participation** | Confirmation | RVOL | Activer / WATCH | Changer la direction |
| **Où ?** | Location | (V1.5) VP, VWAP, S/R via PA | Qualifier l’emplacement | Salade directionnelle |
| **Régime** | Tradable ? | ATR (+ MTF contexte) | Mort / normal / extrême | Voter long/short |
| **Risque** | Sizing | ATR | Stop / size / R:R | Décider la direction |

Catalogue complet + roadmap : [`METHODS-ROADMAP.md`](./METHODS-ROADMAP.md).

---

## 2. Pipeline à étages (pas de multiplication arbitraire)

**Interdit comme règle produit définitive :**

```text
confidence = ichimoku_confidence * rvol_confidence
```

Raccourci MVP (`combiner.py`) → cible = **portes** :

```
ÉTAGE 1 — DIRECTION (setup)
  Ichimoku → LONG / SHORT / NEUTRAL
        │
ÉTAGE 2 — PARTICIPATION
  RVOL ≥ seuil → ACTIF | sinon WATCH
        │
ÉTAGE 3 — STRUCTURE PRIX + MTF
  HH/HL, S/R, BOS… + alignement TF
  → confirme, contre-tendance, ou invalide
        │
ÉTAGE 4 — LOCATION (V1.5)
  VP / VWAP / AVWAP / proximité niveau
  → bon / mauvais emplacement
        │
ÉTAGE 5 — RÉGIME + RISQUE
  ATR → NO_TRADE si mort/extrême ; sinon hints stop/size
        │
ÉTAGE 6 — LABEL
  BUY | SELL | WATCH | NO_TRADE
```

### Implémentation actuelle vs cible

| Aujourd’hui | Cible |
|-------------|--------|
| `combine_ichimoku_rvol` (produit) | `decision_pipeline` à portes |
| Agents : Ichimoku + RVOL | + PA/MTF + ATR (V1), + VP/VWAP (V1.5) |
| Labels STRONG_* legacy | BUY / SELL / WATCH / NO_TRADE (+ qualité) |

---

## 3. Phases produit

### V1 — maintenant (gratuit, OHLCV)

```
ICHIMOKU + RVOL + PRICE ACTION + MTF + ATR
→ Decision Engine
→ Paper / signal-only
```

Ordre code : pipeline étages → structure_agent → MTF → volatility_agent (ATR).

### V1.5 — Location

```
+ Volume Profile + VWAP / Anchored VWAP
```

### V2 — après preuve V1 (+ data trades/futures publics)

```
+ CVD + OI + Funding
(+ Consensus optionnel seulement si backtest le justifie)
```

### V3 — expérimental

```
Wyckoff · Donchian · ADX (garder ou jeter)
```

**Momentum-as-agent séparé / RSI-MACD :** pas dans le cœur.  
**GrokDesk :** orchestration / eval — pas la stratégie.

---

## 4. Pipeline système

```
     MarketDataAdapter          ExecutionAdapter
     (Binance Vision…)     ≠    (Paper → venue au choix)
            │
            ▼
       DATA ENGINE (Python calcule tout)
            │
            ▼
       DECISION ENGINE (5 questions)
            │
     ┌──────┴──────┐
   WATCH         TRADE / signal
                   │
                   ▼
              PAPER → RESULT → PERF / BACKTEST / CALIB
```

Data levels N1 OHLCV → N2 trades → N3 derivatives : [`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md).

Détail PaperBroker / ShadowBroker / Structure consensus / multi-portfolio : [`ARCHITECTURE-CONSOLIDEE-V2.md`](./ARCHITECTURE-CONSOLIDEE-V2.md).

---

## 5. StrategyAgents vs Copilot LLM

| Couche | Rôle | LLM ? |
|--------|------|-------|
| **A. Strategy / indicateurs** | Répondre aux 5 questions, décision | **Non** |
| **B. Copilot** | Expliquer, KB, actions confirmées | **Oui** |

Détail UI : [`APP-ARBORESCENCE-V2.md`](./APP-ARBORESCENCE-V2.md).

---

## 6. Socle réel

| Couche | État |
|--------|------|
| Feed `data-api.binance.vision` | OK (market data only) |
| Ichimoku + RVOL + screener | OK |
| Combiner produit | MVP → remplacer |
| PA / MTF / ATR / VP / VWAP | À construire selon roadmap |
| Execution live CEX | **Hors scope** ; pas hardcodé Binance trade |

---

## 7. Règles non négociables

1. Direction = Ichimoku (+ invalidation structure/MTF), pas RVOL/ATR/LLM.  
2. RVOL = porte participation.  
3. Location = qualité d’emplacement (VP/VWAP/S/R).  
4. ATR = régime + risque, pas direction.  
5. Pas de salade RSI/MACD/Stoch en votes.  
6. Consensus multi-agents après preuve, pas avant.  
7. StrategyAgent ≠ Copilot.  
8. Paper avant live.  
9. **Market data ≠ execution** ; indicateurs = Python sur brut ; zéro abonnement pour le cœur crypto.  
10. **MCP TradingView / charts** = interaction & visualisation uniquement — **pas** un indicateur ni un vote dans le Decision Engine.  
11. **MCP MT5 / exécution réelle** = post-validation (après backtest + Paper + Shadow) — jamais avant preuve.
