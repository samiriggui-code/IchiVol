# Analyse — 3 moteurs Market Structure (réutilisation IchiVol)

**Date :** 2026-09-18  
**Clones locaux (gitignorés) :** `_research/trend-line-detector` · `_research/trendln` · `_research/pytrendline`  
**Cible produit :** [`ARCHITECTURE-CONSOLIDEE-V2.md`](./ARCHITECTURE-CONSOLIDEE-V2.md) §3–4

---

## Verdict en une phrase

**MVPP** = moteur principal à porter (causal + sans yfinance) · **trendln** = second opinion rapide (MIT) · **pytrendline** = validation / breakout **offline only** (O(N³)).

---

## Où sont les clones

```text
_research/
  trend-line-detector/   # mvpp — https://github.com/mvpp/trend-line-detector
  trendln/               # GregoryMorse — https://github.com/GregoryMorse/trendln
  pytrendline/           # ednunezg — https://github.com/ednunezg/pytrendline
```

Ne **pas** committer `_research/` (déjà dans `.gitignore`).

---

## Comparatif

| Critère | MVPP | trendln | pytrendline |
|---------|------|---------|-------------|
| Rôle IchiVol | `MvppStructureAdapter` (primaire) | `TrendlnStructureAdapter` (2ᵉ avis) | Offline / cache nightly |
| Volume | ✅ SMA20 · high-vol 1,5× · wick/body | ❌ | ❌ |
| Min touches | 3 | ≥3 | `min_points_required=3` |
| Breakout | candle-through | aire sous ligne | ✅ `breakout_tolerance` |
| Dédup | 5 critères | `merge_lines` | clustering 2D |
| Complexité | O(P²×N) pivots | O(E² log E) / fenêtre 125 | **O(N³)** |
| Screener 40×TF | OK + cache | OK fenêtre 200–500 | **Non** hot path |
| Licence | **Aucune déclarée** | MIT | MIT |
| Data feed repo | yfinance → **DISCARD** | optionnel yfinance | CSV/fixtures |

---

## A — mvpp/trend-line-detector

### Pipeline

```text
OHLCV → volume_classifier → pivot_detector (Williams Fractals)
     → trend_fitter (min 3 touches, scoring, dédup) → (viz)
```

### Fichiers utiles

| Fichier | Action IchiVol |
|---------|----------------|
| `config.py` | → `StructureMvppParams` |
| `volume_classifier.py` | **PORT** (logique) |
| `pivot_detector.py` | **PORT + rewrite causal** (lookahead fractal/bounce) |
| `trend_fitter.py` | **PORT** cœur métier |
| `data_fetcher.py` / `visualizer.py` / `main.py` | **DISCARD** |

### Paramètres clés

- Volume SMA **20**, high-vol **> 1,5 × SMA** (identique au seuil RVOL IchiVol → **risque double comptage**)
- Fractals `left_span=right_span=5` · `min_touches=3` · tolérance touch **1 %** du range pivots
- Score = touches × volume × span × récence

### Attention

1. **Pas causal** tel quel — rewrite comme `structure.py` (confirmé à `j + right_span`).
2. **Licence absente** — ne pas copier-coller en prod sans accord auteur ; sinon clean-room des idées.
3. Tolérance % prix → recalibrer en **`ATR × k`**.
4. Scoring volume : retirer ou brancher sur `RvolState` unique — pas `RVOL +20` et `vol trendline +20`.

---

## B — GregoryMorse/trendln

### API

- `calc_support_resistance()` — entrée principale (`trendln/__init__.py`)
- `get_extrema()` · `get_levels()` · `get_horizontal_levels()`
- Défaut trendlines : `METHOD_NSQUREDLOGN` · `window=125` · `errpct=0.005`

### Réutiliser

- Extrema + S/R diagonales + **horizontales** + `get_levels` (niveaux au bar courant)
- Dépendances utiles : numpy, findiff — **pas** matplotlib en hot path

### Ne pas

- Méthodes Hough / `METHOD_NCUBED` en screener
- Plotting / yfinance demo

### Rôle

Second opinion **sans volume** → géométrie pure dans le consensus (complète MVPP sans double-compter RVOL).

---

## C — ednunezg/pytrendline

### API

- `CandlestickData` + `detect()` → DataFrames support/résistance + ranks + breakouts
- `min_points_required=3` · `ignore_breakouts=True` · tolérances ≈ % de `avg_candle_range`

### Réutiliser (idées / offline)

- Logique **breakout** → alimenter Breakout/Retest Engine
- `_mark_duplicates` / `is_best_from_duplicate_group` → inspirer StructureConsensus
- Scoring `overall_rank`

### Ne pas

- Appeler `detect()` exhaustif dans le screener live (500³ ops/appel)
- Si offline : N ≤ 150–200, pivots only (`first_pt_must_be_pivot` + `last_pt_must_be_pivot`)

### Bugs

`CandlestickData` : `set_index`/`rename` sans réaffectation — normaliser l’index côté adapter IchiVol.

---

## Plan d’intégration (Phase 2)

```text
MarketDataProvider.fetch_ohlcv()
        │
   ┌────┴────┐
   ▼         ▼
 MVPP     trendln (fenêtre ~300, NSQUREDLOGN)
 (cache)  (batch)
   │         │
   └────┬────┘
        ▼
  StructureConsensus → ZONES (ATR × k)
        ▲
        │ offline / nightly
   pytrendline (N≤150, pivots, top-3 ranked)
```

### Cible code (proposée)

```text
ichivol-app/engine/app/structure/
  types.py                 # MarketStructure, Zone, Trendline
  detector.py              # Protocol StructureDetector
  consensus.py             # StructureConsensusEngine
  params.py
  adapters/
    mvpp.py
    trendln.py
    pytrendline.py         # offline flag
```

### Ordre d’implémentation

1. Types + Protocol + tests synthétiques  
2. `MvppStructureAdapter` (causal, ATR tol, volume via RVOL ou sans score vol)  
3. `TrendlnStructureAdapter` (MIT, wrap lib ou port léger)  
4. Consensus zones  
5. pytrendline offline + expérience `STRUCTURE_*`  
6. Breakout / Retest engines  

### Expériences multi-portfolio (rappel)

```text
STRUCTURE_MVPP · STRUCTURE_TRENDLN · STRUCTURE_PYTRENDLINE · STRUCTURE_CONSENSUS
```

Ne pas présumer que Consensus gagne.

---

## Décisions à trancher avant code

| Sujet | Recommandation |
|-------|----------------|
| Licence MVPP | Contacter auteur **ou** clean-room | 
| Volume MVPP vs RVOL | Une seule source ; score ligne **sans** re-bonus volume |
| Hot path screener | MVPP + trendln seulement ; pytrendline offline |
| Tolérances | Toutes en `ATR × k` |
| Remplacer `structure.py` ? | **Non** — garder HH/HL/BOS ; MVPP ajoute lignes/zones |

---

## Prochaine action concrète

**Phase 1 PaperBroker = déployée VPS (2026-09-18).**  
**Phase 2 skeleton = dans l’engine** (`ichivol-app/engine/app/structure/`) :

| Module | Rôle |
|--------|------|
| `adapters/mvpp.py` | Clean-room causal (fractals + wick/body, score **sans** volume) |
| `adapters/trendln.py` | Second avis géométrique + horizontales |
| `adapters/pytrendline.py` | Offline capped (`pytrendline_max_bars`) |
| `consensus.py` | Zones ATR |
| `breakout.py` / `retest.py` | Candidats breakout / retest |
| `GET /api/engine/structure/{symbol}` | Endpoint analyse |

Smoke checklist Paper : [`PLAN-PAPER-BROKER-MULTI-PORTFOLIO.md`](./PLAN-PAPER-BROKER-MULTI-PORTFOLIO.md).

Suite Phase 2 : ~~brancher structure dans le pipeline / profils expérimentaux `STRUCTURE_*`~~ **fait** (`strategy_profiles.py`, `structure/gate.py`, multi-portfolio sync).

Prochaine étape : déployer engine VPS pour seed des portefeuilles expérimentaux, ou Phase 3 (Context RSI/CMF/Regime modules).
