# Event Intelligence Layer — Audit d’architecture (IchiVol V3)

**Statut** : PHASE 1–4 (audit + architecture + contrats). **Aucune intégration moteur.**  
**Branche** : `cursor/event-intelligence-audit-a2fe`  
**Date** : 2026-09-23  

**Question directrice**  
> Comment intégrer cette Event Intelligence Layer à la vraie architecture actuelle d’IchiVol sans casser la causalité, sans dupliquer les trois pipelines existants et sans transformer Claude ou les news en moteur de trading ?

**Réponse courte**  
Traiter l’Event Layer comme un **quatrième flux d’observation** (à côté des indicateurs, du pipeline de décision, et de Claude-explication) :  
1) détecter l’anomalie **quantitativement** et causalement (REGISTRY / `scan_symbol` / FeatureBar) ;  
2) enrichir le **contexte** (calendar, news, earnings) **sans voter** ;  
3) laisser Claude **expliquer** avec des faits déjà calculés.  
Ne jamais brancher news/calendrier/Claude dans `combine_ichimoku_rvol`, `_final_decision`, ni `apply_context_gate` par défaut.

---

## 1 — Audit IchiVol (PHASE 1)

### 1.1 Carte des couches actuelles

```
OHLCV (providers + resolve_and_fetch)
        │
        ▼
REGISTRY.compute_many  ←  source unique indicateurs (live / Lab / agent)
        │
        ├── ichimoku_agent + rvol_agent
        │         ▼
        │   combine_ichimoku_rvol  →  decision legacy (BUY/SELL/…)
        │         ▼
        │   build_pipeline         →  BUY|SELL|WATCH|NO_TRADE (stages)
        │         ▼
        │   EvidenceEngine         →  stats historiques (ne décide pas)
        │
        ├── app/context/calendar.py  ──┐
        ├── app/context/news.py        ├── CONTEXTE (jamais importé par pipeline)
        └── app/context/gate.py        └── paper profile (downgrade only, optionnel)
                │
                ▼
        Agent channel (read-only tools) → Claude Agent (explication)
```

### 1.2 Où vivent les pièces clés

| Domaine | Chemins | Notes |
|---------|---------|--------|
| Indicateurs | `engine/app/indicators/registry.py`, `ichimoku.py`, `rvol.py`, `atr.py`, … | Contrat : champ `i` = f(candles[0..i]) |
| FeatureBar (Lab) | `engine/app/strategy_lab/features.py` | Analytics/PPO/best_cloud : **pas** des votes live |
| Combiner | `engine/app/decision/combiner.py` | Labels legacy + confidence |
| Pipeline | `engine/app/decision/pipeline.py` | Stages ; jamais de flip de direction ; CVD/OI enrichissent sans changer le status |
| Live | `engine/app/screener/service.py::scan_symbol` | Assemblage unique décisions HTTP / agent |
| Lab / event-study | `strategy_lab/event_study.py` | `EventObservation` = **signal→forward path**, **pas** macro/news |
| Régimes Lab | `strategy_lab/regime.py::classify_regimes` | ADX+ATR ; research only |
| Calendar | `app/context/calendar.py` → `/context/calendar` + `get_calendar` | ForexFactory weekly JSON ; empty on fail |
| News | `app/context/news.py` | RSS crypto global (pas par symbole) |
| Context gate | `app/context/gate.py` | RSI/CMF/OBV/ATR paper ; **≠** news |
| Claude | `server/src/agent/systemPrompt.ts`, `claudeAgent.ts`, `agent_channel/*` | Engine décide ; Claude explique |
| Paper | `app/paper/*` | `entry_signal` JSON + `evidence_id` |

### 1.3 Trois pipelines — risque de duplication

| Pipeline | Entrée | Core partagé | Divergence |
|----------|--------|--------------|------------|
| Live | `scan_symbol` | REGISTRY + agents + pipeline | OI/MTF/CVD complets |
| Lab / backtest | `prepare_variants`, `build_feature_series` | Même REGISTRY + `build_pipeline` pour PIPELINE | FeatureBar plus riche |
| API / agent | serializers + commandes | Même payload | Persist defaults différents |

**Règle d’intégration** : un seul compute causal (module `app/events/` ou indicateur REGISTRY) appelé depuis `scan_symbol` **et** Lab — jamais une copie TS, jamais seulement Lab, jamais seulement un outil Claude.

### 1.4 Ce qui ressemble déjà à une « anomalie »

- **RVOL** : `AnomalyLevel` LOW→ANOMALY ; `vol_accel`, percentile — **participation**, pas événement externe.  
- **ATR** : régimes DEAD/NORMAL/EXTREME — volatilité technique.  
- **Lab regimes** : TRENDING/RANGING/VOL — research.  

→ L’Event Anomaly Detector doit **composer** avec RVOL/ATR (features), pas les remplacer, et produire un objet **séparé** (`MarketRegime = NORMAL|EVENT|UNKNOWN_EVENT`).

### 1.5 Naming collision critique

`strategy_lab.event_study.EventObservation` = observation d’un **signal d’entrée** et de son chemin forward (MFE/MAE).  

**Ne pas réutiliser ce nom** pour les événements macro/news. Proposer : `MarketAnomalyObservation`, `ExternalEventMatch`, `EventContextBundle`.

### 1.6 Interdits absolus (préservés)

- Importer calendar/news dans `decision/pipeline.py` ou `combiner.py`
- Faire voter Claude / FinBERT / headlines en BUY/SELL
- Affaiblir les tests de lookahead pour « faire passer » un modèle
- Brancher une anomalie comme stage `FAIL` qui change `_final_decision` sans étude empirique préalable

---

## 2 — Audit des repos de référence (PHASE 2)

Clones locaux : `/tmp/event-intel-audit/` (lecture seule, hors git IchiVol).

### 2.1 Synthèse KEEP / ADAPT / REJECT

| Repo | Verdict | Justification |
|------|---------|---------------|
| **ai-market-event-detector** | **ADAPT (forme) / REJECT (impl)** | Forme idéale : detect → news → LLM explain. **Rejeter** Isolation Forest `fit_predict` sur toute la série, news ±2 jours (fuite future), features jouets, Gemini. |
| **stock-anomaly-detector** | **KEEP (cœur quantitatif)** | Features causales `shift(1).rolling`, tests anti-leakage, règles + consensus. Meilleure base pour `EventAnomalyDetector`. |
| **UnusualVolumeDetector** | **ADAPT (volume)** | Médiane passée × multiplicateur + liquidité. Aligner avec RVOL existant ; pas un système complet. |
| **finBERT** | **ADAPT (étroit)** | Tone optionnel en métadonnée. **Jamais** BUY/SELL. |
| **finbert-analyze-financial-news** | **ADAPT ingest / REJECT intent** | Pattern Tiingo + `publishedDate`. Rejeter sentiment→direction. |
| **news-event-impact-detector** | **ADAPT classifier / REJECT impact** | Taxonomie + fine-tune multi-classe. Rejeter `predicted_return` comme signal. |
| **earnings** (lcsrodriguez) | **ADAPT concept / REJECT client** | Idée calendrier earnings. Ne pas shipper le scraper EarningsWhispers (ToS/bugs). Provider licencié + timezones BMO/AMC. |

### 2.2 Détail — ai-market-event-detector (prioritaire)

- Features : `return`, `volatility=rolling(7).std()` (inclut t), `volume_change`
- IF `contamination=0.02` sur **toute** la fenêtre → non causal
- News : anomalie ±2 jours → **lookahead news**
- LLM : Gemini post-hoc (séparé de la détection) → **garder la séparation**, remplacer par Claude Agent IchiVol

**Pour IchiVol** : voler l’architecture narrative ; reconstruire la détection avec le pattern stock-anomaly + RVOL/ATR.

### 2.3 Détail — stock-anomaly-detector (cœur)

| Feature | Définition causale |
|---------|-------------------|
| `ret_z` | z-score return vs `.shift(1).rolling(63)` |
| `vol_z` | z-score log-volume vs fenêtre passée |
| `range_pct` | percentile empirique passé de (H−L)/C |

Règles : `|ret_z|>2.5` OR `vol_z>2.5` OR `range_pct>0.95` → types spike/crash/volume_shock.  
Tests : `test_return_zscore_no_leakage` — **à répliquer**.

### 2.4 UnusualVolumeDetector

`volume_t >= median(volume[t-20:t-1]) * N` — déjà l’esprit de RVOL.  
Garder l’idée de floors liquidité ; calibrer N **par classe d’actifs / TF** (pas copier 3×).

### 2.5 FinBERT / finbert-news / impact / earnings

- FinBERT = ton, pas événement.  
- Impact detector = excellent gabarit `EventClassifier` (labels utilisateur) ; **couper** la régression de rendement.  
- Earnings = `CorporateEventProvider` via API propre (Twelve Data / provider déjà payé si dispo), pas le client EW.

---

## 3 — Architecture cible (PHASE 3)

### 3.1 Principe

```
                 OHLCV (closed bars only)
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
   TECHNICAL        ANOMALY         CONTEXT
   ENGINE           DETECTOR        PROVIDERS
   (existant)       (nouveau)       (étendu)
         │              │              │
         │              ▼              │
         │     MarketAnomalyObservation
         │     market_regime ∈ {NORMAL, EVENT_MARKET, UNKNOWN_EVENT}
         │              │              │
         └──────────────┼──────────────┘
                        ▼
              EventContextBundle  (CORRELATED_EVENT, jamais PROVEN_CAUSE)
                        │
                        ▼
              SignalContext / ScreenerRow  (champs OBSERVATION)
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
   pipeline.decision  Evidence     Claude Agent
   (INCHANGÉ)         snapshot     (explique avec faits)
```

**EVENT ≠ SIGNAL.** Une anomalie ne produit jamais BUY/SELL.

### 3.2 Modules proposés

| Module | Rôle | Emplacement proposé |
|--------|------|---------------------|
| `EventAnomalyDetector` | Features causales + scores + types de choc | `engine/app/events/anomaly.py` |
| `MarketAnomalyObservation` | Dataclass immutable par barre | `engine/app/events/types.py` |
| `SymbolNewsProvider` | News filtrées symbole + `published_at ≤ T` | `engine/app/events/news.py` (à côté de `context/news.py`) |
| `CorporateEventProvider` | Earnings / corporate calendar | `engine/app/events/corporate.py` |
| `MacroCalendarProvider` | Wrap `fetch_calendar_events` + filtre impact/temps | `engine/app/events/macro.py` |
| `EventClassifier` | Headline → taxonomie (pas sentiment→trade) | `engine/app/events/classifier.py` |
| `EventCorrelationEngine` | Proximité temporelle + relevance → match confidence | `engine/app/events/correlate.py` |
| `EventContextBundle` | Agrégat anomaly + matches | `engine/app/events/context.py` |
| `ClaudeEventExplainer` | **Pas un module Python** — prompt + outils agent read-only | `server/src/agent/*` + `get_event_context` |

### 3.3 Régimes marché

| Régime | Condition | Comportement produit |
|--------|-----------|---------------------|
| `NORMAL_MARKET` | Pas d’anomalie (ou scores sous seuils calibrés) | Analyse IchiVol classique |
| `EVENT_MARKET` | Anomalie **et** match externe (calendar/news/earnings) avec confidence ≥ seuil | Afficher TECHNICAL_SIGNAL + EVENT_TYPE ; **ne pas** booster en SUPER_BUY |
| `UNKNOWN_EVENT` | Anomalie **sans** match explicatif | « ABNORMAL MOVE — CAUSE UNKNOWN » ; confirmation supplémentaire côté UX / evidence, **pas** auto-force trade |

### 3.4 Types d’anomalie (sans news)

`PRICE_SHOCK` · `VOLUME_SHOCK` · `GAP_EVENT` · `VOLATILITY_SHOCK` · `PRICE_VOLUME_SHOCK` · `NONE`

Features candidates (toutes causales, past-only) :

- `return_zscore`, `volume_zscore`, `range_vs_atr`, `gap_vs_atr`, `rvol`, `volatility_zscore`

**Calibration (non arbitraire)** — PHASE 6 avant seuils live :

1. Collecter distributions **par** `(asset_class, timeframe)` sur historique causal.  
2. Estimer quantiles empiriques (ex. 99.0 / 99.5) **out-of-sample** (walk-forward).  
3. Publier une table de seuils versionnée (`EVENT_FEATURE_VERSION`) — même esprit que `FEATURE_VERSION` evidence.  
4. Ne **pas** utiliser Isolation Forest full-fit comme stock ai-market ; si ML unsupervised un jour : expanding window + train≤T uniquement (pattern stock-anomaly).

### 3.5 Taxonomie EventClassifier

`MACRO_EVENT` · `EARNINGS` · `GUIDANCE` · `M&A` · `REGULATORY` · `LEGAL` · `PRODUCT` · `MANAGEMENT` · `ANALYST_RATING` · `GEOPOLITICAL` · `CENTRAL_BANK` · `ECONOMIC_DATA` · `CRYPTO_SPECIFIC` · `UNKNOWN`

Première question du classifier :  
> « Existe-t-il un événement assez pertinent (temps + sémantique) pour **expliquer** l’anomalie ? »  
Pas : « Est-ce bullish ? »

### 3.6 Corrélation ≠ causalité

Le moteur émet `CORRELATED_EVENT` avec :

- `temporal_proximity` (Δt, news **≤** T0 seulement)
- `symbol_relevance`
- `event_category`
- `source_reliability`
- `event_match_confidence`

Jamais `PROVEN_CAUSE`.

### 3.7 Points d’insertion sûrs

| Couche | Où | Comment |
|--------|-----|---------|
| Quantitatif | Après REGISTRY dans `scan_symbol` ; miroir Lab `build_feature_series` | Champ `anomaly` / `event_context` sur row |
| Evidence | `SignalContext` / `market_snapshot` | Version bump `feature_version` |
| API | `/context/...` + serializer décisions (lecture) | Opt-in |
| Agent | Nouvelle cmd `get_event_context` read-only | Claude choisit de l’appeler |
| Pipeline / combiner | **Aucun changement** en PHASE 7 sans résultats event-study | — |

Pattern existant à copier : **CVD/OI** enrichissent les *codes* participation sans changer `StageStatus`.

### 3.8 Event study (PHASE 6) — avant toute règle

Réutiliser l’infra `strategy_lab/event_study.py` (MFE/MAE, horizons) en **stratifiant** les signaux IchiVol par `market_regime` au bar de signal :

- continuation N barres  
- reversal / false breakout  
- MFE / MAE  

Comparer `NORMAL_MARKET` vs `EVENT_MARKET` vs `UNKNOWN_EVENT`.  
**Mesurer d’abord** ; ne pas changer les gates « parce que ça semble logique ».

---

## 4 — Contrats Python (PHASE 4)

Esquisse (non commitée dans le runtime — référence de design) :

```python
# app/events/types.py (proposé)

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

class MarketRegime(str, Enum):
    NORMAL_MARKET = "NORMAL_MARKET"
    EVENT_MARKET = "EVENT_MARKET"
    UNKNOWN_EVENT = "UNKNOWN_EVENT"

class AnomalyType(str, Enum):
    NONE = "NONE"
    PRICE_SHOCK = "PRICE_SHOCK"
    VOLUME_SHOCK = "VOLUME_SHOCK"
    GAP_EVENT = "GAP_EVENT"
    VOLATILITY_SHOCK = "VOLATILITY_SHOCK"
    PRICE_VOLUME_SHOCK = "PRICE_VOLUME_SHOCK"

class EventCategory(str, Enum):
    MACRO_EVENT = "MACRO_EVENT"
    EARNINGS = "EARNINGS"
    GUIDANCE = "GUIDANCE"
    M_AND_A = "M&A"
    REGULATORY = "REGULATORY"
    LEGAL = "LEGAL"
    PRODUCT = "PRODUCT"
    MANAGEMENT = "MANAGEMENT"
    ANALYST_RATING = "ANALYST_RATING"
    GEOPOLITICAL = "GEOPOLITICAL"
    CENTRAL_BANK = "CENTRAL_BANK"
    ECONOMIC_DATA = "ECONOMIC_DATA"
    CRYPTO_SPECIFIC = "CRYPTO_SPECIFIC"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True)
class MarketAnomalyObservation:
    symbol: str
    timeframe: str
    bar_time: int                 # open time of closed bar
    event_suspected: bool
    event_type: AnomalyType
    return_zscore: float | None
    volume_zscore: float | None
    range_atr_ratio: float | None
    gap_atr_ratio: float | None
    rvol: float | None
    volatility_zscore: float | None
    confidence: float             # [0,1] from calibrated scores
    feature_version: str

@dataclass(frozen=True)
class ExternalEventRef:
    source: str                   # "macro_calendar" | "symbol_news" | "corporate"
    category: EventCategory
    title: str
    published_at: int             # unix ; MUST be <= bar_time for match
    url: str | None
    symbol_relevance: float
    temporal_proximity_s: int
    match_confidence: float
    relation: str = "CORRELATED_EVENT"  # never PROVEN_CAUSE

@dataclass(frozen=True)
class EventContextBundle:
    anomaly: MarketAnomalyObservation
    market_regime: MarketRegime
    matches: Sequence[ExternalEventRef]
    disclaimer: str = (
        "Contexte événementiel — n'est pas un signal d'achat/vente."
    )
```

```python
# Signatures proposées

def detect_anomaly(
    candles: Sequence[Candle],   # closed only
    *,
    symbol: str,
    timeframe: str,
    rvol_series: Sequence[float] | None = None,
    atr_series: Sequence[float] | None = None,
    thresholds: AnomalyThresholds,
) -> MarketAnomalyObservation:
    """Pure ; bar last index only uses candles[0..-1] history causally."""
    ...

def correlate_events(
    anomaly: MarketAnomalyObservation,
    candidates: Sequence[ExternalEventRef],
    *,
    max_lag_s: int,
) -> EventContextBundle:
    """Drop any candidate with published_at > anomaly.bar_time."""
    ...
```

### Anti-lookahead (PHASE 5 — tests à écrire avant merge code)

1. Truncation : préfixe candles → mêmes scores aux indices communs.  
2. News future : injecter headline `T+1` → ne doit **pas** apparaître dans matches à `T`.  
3. Threshold fit : calibrer sur train ; scores test ne re-fittent pas.  
4. Forming bar : exclure la bougie ouverte (même règle que `decide_on_closed_candles` / T0-CALC `closed_candles`).

---

## 5 — Plan d’exécution (rappel des phases)

| Phase | Contenu | État |
|-------|---------|------|
| 1 | Audit IchiVol | **fait** (ce doc) |
| 2 | Audit repos externes KEEP/ADAPT/REJECT | **fait** |
| 3 | Architecture modules + insertion points | **fait** |
| 4 | Contrats Python | **fait** (design) |
| 5 | Tests causaux / anti-lookahead | **à faire** (avant code live) |
| 6 | Backtest / event-study NORMAL vs EVENT | **à faire** |
| 7 | Intégration moteur (observation only) | **bloquée** tant que 5–6 non verts |

### Première tranche de code recommandée (quand autorisée)

1. `app/events/` + `detect_anomaly` (règles causales, seuils **placeholder versionnés** + harness de calibration).  
2. Tests lookahead dédiés.  
3. Branchement **read-only** sur `scan_symbol` / serializer / `get_event_context`.  
4. **Zéro** changement `_final_decision`.  
5. Ensuite seulement : SymbolNewsProvider + correlate + Claude tool.

---

## 6 — Réponse à la question directrice (détaillée)

1. **Causalité** : même contrat que REGISTRY + closed bars ; features `shift(1)` ; news `published_at ≤ T` ; tests truncation obligatoires.  
2. **Pas de triple duplication** : un module `app/events` appelé par live **et** Lab ; exposition agent = wrap HTTP, pas une 2ᵉ implémentation.  
3. **Pas de trading par news/Claude** :  
   - calendar/news restent hors `pipeline.py` ;  
   - FinBERT/sentiment = métadonnée ;  
   - Claude reçoit `EventContextBundle` déjà calculé et explique ;  
   - régime `UNKNOWN_EVENT` empêche de transformer un RVOL 7 en SUPER_BUY.  
4. **Compatibilité produit** : le Signal Engine reste l’autorité des observations techniques ; l’Event Layer **qualifie l’environnement** ; Claude **explique**.

---

## 7 — Hors scope immédiat

- Transformer Claude en oracle de marché  
- Sentiment trading  
- Isolation Forest non causal  
- Scraper EarningsWhispers  
- Modifier les gates paper/live sans event-study  
- Réutiliser le nom `EventObservation` du Strategy Lab  

---

*Document d’architecture uniquement. Aucun changement runtime dans cette PR.*
