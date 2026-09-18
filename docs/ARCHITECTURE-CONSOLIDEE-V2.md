# ICHIVOL — Architecture consolidée V2

**Statut :** source de vérité du *lab quantitatif* (paper / shadow / structure / expériences)  
**Date :** 2026-09-18  
**North star produit (5 questions) :** [`TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md) — reste verrouillé  
**Exécution Phase 1 PaperBroker :** [`PLAN-PAPER-BROKER-MULTI-PORTFOLIO.md`](./PLAN-PAPER-BROKER-MULTI-PORTFOLIO.md)  
**Data ≠ execution :** [`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md)

---

## OBJECTIF

Faire évoluer IchiVol d’un simple moteur **Ichimoku × RVOL** vers un laboratoire quantitatif capable de :

* lire la structure du marché ;
* détecter les zones importantes ;
* mesurer tendance, volume, volatilité et momentum ;
* produire `WATCH` / `LONG` / `SHORT` / `NO_TRADE` ;
* simuler les décisions avec un portefeuille fictif ;
* comparer plusieurs variantes de stratégie ;
* déterminer statistiquement quelles briques apportent réellement de la valeur.

**AUCUN ordre réel.**

Tout reste : **ANALYSE + PAPER TRADING + SHADOW TRADING + BACKTEST + VALIDATION.**

---

## Glossaire (anti-collision de noms)

| Terme | Sens canonique IchiVol |
|-------|------------------------|
| **PaperBroker** | Compte fictif capitalisé (5 000 €), fills, cash, SL/TP, journal. Affecte l’equity. |
| **ShadowBroker** | Trades *counterfactuels* (ex. signal LONG bloqué par résistance) — **n’affectent pas** le cash. Servent à mesurer l’utilité des filtres. |
| **Auto paper** | Positions paper `source=auto_watchlist` (screener). Ce n’est **pas** le ShadowBroker. |
| **Shadow mode** (`INTEGRATION_PLAN`) | Pipeline live **sans aucune** exécution (ni paper ni réel). |
| **AgentChannel** | Pattern d’orchestration type `_research/Shadowbroker/` (handoff Claude). **Pas** un broker de trading. |
| **tradingview-mcp** | Couche interaction / visualisation. **Pas** un indicateur du Decision Engine. |
| **MCP MT5** | Bridge exécution éventuel. **Post-validation** uniquement. |

---

## 1. Architecture globale (corrigée)

Le schéma « Core + Structure → Decision → Shadow 5 000 € » est le bon *esprit*, avec trois corrections obligatoires :

1. Le compte 5 000 € = **PaperBroker**, pas ShadowBroker.  
2. Fibonacci **n’est pas** dans Market Structure (pas d’« angle Fib » dans la géométrie).  
3. ATR sert à **normaliser** (zones, breakout, stops) et au **risque** — pas seulement à la structure.

```text
                         OHLCV (MarketDataProvider)
                                   │
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
        ICHIVOL CORE                            STRUCTURE ENGINE
     Ichimoku + RVOL                    ┌───────┼───────┐
              │                         ▼       ▼       ▼
              │                       MVPP   trendln  pytrendline
              │                         └───────┼───────┘
              │                                 ▼
              │                        STRUCTURE CONSENSUS
              │                     zones S/R · swings · TL
              │                     breakout / retest
              └────────────────────┬────────────────────┘
                                   ▼
                            CONTEXT ENGINES
                 ATR · RSI · CMF/OBV · FibonacciContext*
                                   ▼
                             REGIME ENGINE
                                   ▼
                           CONFLUENCE → DECISION
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
            WATCH               TRADE               NO_TRADE
                                   │                    │
                                   ▼                    ▼
                             RISK ENGINE          SHADOW BROKER
                                   │              (counterfactual,
                                   ▼               hors cash)
                             PAPER BROKER
                               5 000 €
                          SL/TP · sizing · fees
                                   │
                                   ▼
                            TRADE JOURNAL
                                   │
                                   ▼
                          PERFORMANCE ENGINE
                                   │
                                   ▼
                        EXPERIMENT COMPARATOR
                     KEEP / REJECT / INVESTIGATE

* Fibonacci reçoit les swings du Structure Engine — ne les invente pas.

──────────────── INTERACTION / VIZ (hors décision) ────────────────
  App charts (lightweight-charts)
  tradingview-mcp  →  yeux + UI, pas un vote indicateur
  MCP MT5          →  post-validation only (live/bridge)
```

---

## 2. Market Structure Engine

Moteur **indépendant** — ne remplace **pas** Ichimoku.

```text
ICHIMOKU
→ Dans quelle structure/tendance générale évolue le marché ?

MARKET STRUCTURE
→ Où sont les zones auxquelles le prix réagit réellement ?
```

Sorties cibles :

```text
swings_high / swings_low
pivot_high / pivot_low
support_levels / resistance_levels   → idéalement ZONES (pas prix magiques)
support_trendlines / resistance_trendlines
breakout_candidates / retest_candidates
distance_to_support / distance_to_resistance
structure_score
```

État actuel code : `engine/app/indicators/structure.py` = swings HH/HL + BOS seulement.  
Cible : zones + trendlines + consensus multi-détecteurs.

---

## 3. Trois repositories structure (analyse, pas data feed)

**Analyse détaillée (2026-09-18) :** [`ANALYSE-STRUCTURE-ENGINES.md`](./ANALYSE-STRUCTURE-ENGINES.md)  
**Clones locaux :** `_research/trend-line-detector` · `_research/trendln` · `_research/pytrendline` (gitignorés).

Cloner / analyser, **réutiliser les algos**, injecter `MarketDataProvider.fetch_ohlcv(...)` IchiVol.

| Repo | Rôle | Points à reprendre |
|------|------|--------------------|
| [mvpp/trend-line-detector](https://github.com/mvpp/trend-line-detector) | Moteur principal candidat | Williams Fractals, volume classifier (SMA20, high-vol > 1,5×), wick/body selon volume, ≥3 touches, scoring, dédup |
| [GregoryMorse/trendln](https://github.com/GregoryMorse/trendln) | *Second opinion* | supports / résistances / extrema / horizontales |
| [ednunezg/pytrendline](https://github.com/ednunezg/pytrendline) | Validation / scoring | pivots, `min_points_required`, tolérances breakout, clustering — **attention O(N³)** : fenêtre limitée, cache, recalcul hors chemin hot |

### Double comptage volume

RVOL et volume des trendlines sont **liés**.  
Interdit d’additionner naïvement `RVOL +20` et `Volume trendline +20` pour le même phénomène.

---

## 4. Abstraction + consensus

```python
class StructureDetector:
    def detect(self, ohlcv) -> MarketStructure: ...

# Adapters
MvppStructureAdapter
TrendlnStructureAdapter
PyTrendlineStructureAdapter
```

```text
                 StructureDetector
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
     MVPP           trendln        pytrendline
       │               │               │
       └───────────────┼───────────────┘
                       ▼
              STRUCTURE CONSENSUS  →  ZONES (ATR-normalized)
```

Score de zone : nb moteurs d’accord · touches · récence · volume · distance ATR · durée · retests.

Tolérances : `ZONE_TOLERANCE = ATR × coefficient` (jamais `± 2 €` fixe).

---

## 5. Breakout / Retest

Une cassure **n’est pas** `price > resistance`.

Observer : close beyond · distance / ATR · RVOL · body · régime · retest éventuel.

```text
BREAKOUT → RETURN TO LEVEL → RETEST → HOLD / FAILURE
```

Setup candidat : `SETUP_BREAKOUT_RETEST`.

---

## 6. Fibonacci — correction

**Ne pas** mettre « Fibonacci angle » dans Market Structure.

```text
Market Structure (swings)
        ↓
FibonacciContextEngine
  23.6 · 38.2 · 50 · 61.8 · 78.6
        ↓
Confluence Engine
```

Fib mesure le retracement **dans** une structure déjà trouvée.

---

## 7. Confluence (exemple d’explication)

```text
XAUUSD — H1
ICHIMOKU … BULLISH
RVOL 1.83 STRONG
MARKET STRUCTURE  support 3648–3655 · resistance 3720–3726 · TL valid · 4 touches
FIBONACCI  61.8 % confluence YES
ATR NORMAL · RSI pos · CMF pos · REGIME TREND_UP
DECISION LONG · confidence 78/100
→ Risk Engine → PaperBroker
```

Chaque trade journalise un JSON d’explainability (ichimoku, rvol, market_structure, fibonacci, régime, decision, risk_pct).

---

## 8. PaperBroker

Capital initial : **5 000 €** / portefeuille.

Gère : cash · equity · positions · sizing · entry · SL · TP · spread · fees · slippage · P&L réalisé/non réalisé · drawdown.

Sizing = `capital × risk% / stop_distance` — jamais un montant arbitraire.

**Décision Phase 1 (validée 2026-09-18) :** risk **1 %** · TP **2R** · max **5** opens · `USDT ≈ EUR` proxy.  
L’exemple pédagogique 0,5 % / 25 € reste illustratif pour d’autres profils expérimentaux — **ne remplace pas** le freeze baseline.

---

## 9. ShadowBroker (counterfactual)

Quand le Decision Engine dit `NO_TRADE` (ex. Ichimoku LONG + RVOL OK mais résistance proche → BLOCK), le ShadowBroker ouvre quand même un **SHADOW_LONG** hors portefeuille.

Après N cas : mesurer si le filtre a évité plus de pertes que de gains — sinon le filtre est trop agressif.

---

## 10. Multi-portfolio (expérience principale)

Tous démarrent à **5 000 €**, même marché / timestamp / OHLCV / frais / politique de risque de base.

```text
PORTFOLIO A  Ichimoku seul
PORTFOLIO B  Ichimoku + RVOL              = ICHIVOL_BASELINE_V1
PORTFOLIO C  IchiVol + ATR
PORTFOLIO D  IchiVol + Market Structure
PORTFOLIO E  IchiVol + Market Structure + Regime
PORTFOLIO F  IchiVol + Market Structure + Fibonacci
PORTFOLIO G  IchiVol Full
```

Expérience structure séparée :

```text
STRUCTURE_MVPP · STRUCTURE_TRENDLN · STRUCTURE_PYTRENDLINE · STRUCTURE_CONSENSUS
```

Ne **pas** supposer que Consensus gagne — le tester.

**Règle :** ne jamais écraser `ICHIVOL_BASELINE_V1`. Les nouvelles architectures tournent en parallèle.

---

## 11. Métriques (par portefeuille)

Initial / Final equity · Return · Closed trades · Win rate · Avg winner/loser · Profit factor · Expectancy · Sharpe · Sortino · Max DD · Recovery factor · MFE / MAE · Best/Worst market · TF · régime.

---

## 12. Une responsabilité par module

```text
ICHIMOKU        = structure directionnelle
RVOL            = participation
MARKET STRUCTURE= géométrie réelle du prix
ATR             = volatilité / normalisation / risque
RSI             = momentum
CMF / OBV       = flux
FIBONACCI       = retracement / zones potentielles
REGIME          = contexte
RISK ENGINE     = combien risquer
PAPER BROKER    = conséquence financière fictive
SHADOW BROKER   = conséquence counterfactuelle (hors cash)
```

**Pas de soupe d’indicateurs.** Chaque brique = module expérimental jugé hors échantillon.

---

## 13. Couches Interaction / MCP (hors décision)

| Brique | Rôle | Indicateur IchiVol ? | Quand |
|--------|------|----------------------|-------|
| MVPP / trendln / pytrendline | Analyse structure (Python sur OHLCV) | Modules expérimentaux **oui** | Phase 2 |
| App `lightweight-charts` | UI produit | Non | Continu |
| **tradingview-mcp** | Yeux + interaction / viz / inspection | **Non** — n’alimente pas le Decision Engine | Après PaperBroker stable ; parallèle OK avec Phase 2+ |
| Pine `ichimoku-volume/` | Companion chart humain | Non (jumelage TV) | Continu |
| **MCP MT5** | Bridge exécution | Non | **Beaucoup plus tard** — après backtest + Paper + Shadow validés |

Règle produit :

> Le MCP TradingView n’est **pas** un nouvel indicateur IchiVol.  
> Les repos trend-line améliorent l’**analyse** ; tradingview-mcp améliore l’**interaction / visualisation** ; le MCP MT5 est une étape **beaucoup plus tardive**.

Interdit : payer TradingView / APIs d’indicateurs tout faits pour le **cœur** crypto ([`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md)).

---

## 14. Priorité de développement

| Phase | Contenu |
|-------|---------|
| **1** | PaperBroker 5 000 € · Risk · SL/TP · fees · journal · metrics capital · freeze `ICHIVOL_BASELINE_V1` — **DÉPLOYÉ VPS 2026-09-18** |
| **2** | Market Structure · adapters · consensus · breakout/retest · **profils STRUCTURE_*** + gate paper multi-portfolio — **wire livré 2026-09-18** (baseline intact) |
| **3** | Context : ATR (déjà), Regime hard, RSI, CMF/OBV — **profils `ICHIVOL_CTX_*` / `ICHIVOL_MS_REGIME` livrés 2026-09-18** |
| **4** | FibonacciContext · multi-portfolio A–G · expériences `STRUCTURE_*` |
| **5** | ShadowBroker · counterfactuels · walk-forward / OOS |
| *∥* | **Strategy Lab Phase 1 — Event Study** (`app/strategy_lab/`, `GET /event-study/{symbol}`) — forward returns / MFE-MAE ATR **sans capital** ; livré 2026-09-18 |
| *∥* | **Strategy Lab Phase 2 — Rules Engine** (`ruleset` + `POST /ruleset/event-study`) — hypothèse `IV_*` déclarative → occurrences → Event Study ; livré 2026-09-18 |
| *∥* | **Strategy Lab Phase 3 — Ruleset Backtest** (`ruleset_backtest.py`) — SL/TP ATR sur rising-edge ; métriques WR/PF/DD ; livré 2026-09-18 |
| *∥* | **Strategy Lab Phase 4 — Performance DB** (`strategy_lab_experiments`) — persist rules_json + métriques + event study ; list/compare API ; livré 2026-09-18 |
| *∥* | **Strategy Lab Phase 5 — Ablation** (`ablation.py`) — escalier A→E + deltas expectancy/PF ; leave-one-out ; livré 2026-09-18 |
| *∥* | **Strategy Lab Phase 6 — Regime slices** (`regime.py` / `regime_slices.py`) — TRENDING/RANGING/VOL/BULL… ; livré 2026-09-18 |
| *∥* | **Strategy Lab Phase 7 — Walk-forward** (`walk_forward.py`) — rolling/expanding IS/OOS ruleset fixe ; livré 2026-09-18 |
| *∥* | **Strategy Lab Phase 8 — Optimization** (`optimization.py`) — grid-search IS → OOS via walk-forward-opt ; livré 2026-09-18 |
| *∥* | tradingview-mcp (viz only) — ne bloque pas 2–5 |
| *plus tard* | MCP MT5 / exécution réelle |

Critère d’admission d’un module :

> Sur données hors échantillon, avec assez de trades : améliore-t-il expectancy et/ou max DD **sans** dégrader excessivement le drawdown vs `ICHIVOL_BASELINE_V1` ?

---

## Principe final

Ne pas demander « Est-ce que Fibonacci est bon ? » ou « Est-ce que trendln est meilleur ? ».

Demander aux données : **cette information améliore-t-elle réellement IchiVol hors échantillon ?**

PaperBroker + A/B testing + ShadowBroker + walk-forward décident quelles briques intègrent le produit.
