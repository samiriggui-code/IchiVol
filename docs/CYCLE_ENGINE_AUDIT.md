# Cycle / Spectral Engine — Audit d’intégration (IchiVol V3)

**Statut :** chantier ouvert · observe-only  
**Date :** 2026-09-25  
**Règle :** ne change **aucune** gate / paper / confidence tant que walk-forward + ablation + null models hors échantillon n’ont pas prouvé une information **incrémentale**.

Réf. produit : [`CAHIER-DES-CHARGES.md`](./CAHIER-DES-CHARGES.md) · [`METHODS-ROADMAP.md`](./METHODS-ROADMAP.md) · [`TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md)

---

## 0. Question centrale

Est-ce que Cycle Engine apporte à IchiVol une dimension **TEMPS** (phase, horizon, stabilité, régime cyclique) **non redondante** avec Ichimoku × RVOL × Structure × ATR/ADX ?

Réponse **provisoire (pré-backtest)** : **oui comme chantier de recherche**, **non comme vote BUY/SELL**.  
Réponse **définitive** : uniquement après protocole §15–17.

---

## 1. Architecture actuelle réellement trouvée

| Zone | Chemin | Rôle |
|------|--------|------|
| Engine FastAPI | `ichivol-app/engine/app/main.py` | Préfixe `/api/engine` |
| Composition routes | `app/api/routes.py` | Ordre de precedence figé (golden) |
| Indicateurs | `app/indicators/` + `registry.py` | Compute déterministe, statuts CANDIDATE→PRODUCTION/REJECTED |
| Pipeline | `app/decision/pipeline.py` | Direction → Participation → Structure → Location → Régime |
| Combiner legacy | `app/decision/combiner.py` | Ichi×RVOL labels |
| Evidence | `app/evidence/` | Explain, ne invente pas BUY/SELL |
| Context | `app/context/` | News/calendar + gates paper optionnels |
| Correlations | `app/correlation/engine.py` | Pearson stdlib, **jamais** branché pipeline |
| Events / anomaly | `app/events/` | Observation screener/décisions |
| Strategy Lab | `app/strategy_lab/` | Event study, ablation, walk-forward |
| Research offline | `engine/research_lab/` | CLI, non importé par live |
| Agent channel | `app/agent_channel/` | Tools allowlistés read-only |

**Constat :** aucun module FFT / Hilbert / Ehlers / ACF / EMD dans le dépôt (recherche repo-wide).

---

## 2. Indicateurs actuellement présents

### Registry (vote ou gate)

| ID | Statut | Vote direction ? |
|----|--------|------------------|
| `ichimoku` | PRODUCTION | Oui (Direction) |
| `rvol` | PRODUCTION | Gate Participation |
| `structure` | PRODUCTION | Downgrade Structure |
| `location` | PRODUCTION | Downgrade Location |
| `atr` | PRODUCTION | Régime / risque, **pas** LONG/SHORT |
| `adx` | PRODUCTION | Veto régime faible |
| `donchian` | PRODUCTION | Veto breakout non confirmé |
| `cvd` | PRODUCTION | Codes only |
| `rsi` / `cmf` / `obv` | CANDIDATE | Paper context gates only |
| `ppo` / `best_cloud` / `wyckoff` | REJECTED | Lab / hors cœur |
| `impulse` / `fvg` / `ichimoku_analytics` | EXPERIMENTAL | Lab/chart |

### Hors registry

Fibonacci, MTF Ichimoku, structure S/R adapters, OI/funding, anomaly/regime study, family_weights.

**Redondance potentielle avec Cycle :** ATR/ADX/Donchian (régime tradable vs oscillatoire). Cycle doit répondre à **période / phase / stabilité**, pas re-voter « est-ce tradable ? ».

---

## 3. Pipeline actuel

1. **Direction** — Ichimoku agent  
2. **Participation** — RVOL (+ CVD codes)  
3. **Structure** — PA/BOS + MTF  
4. **Location** — VP / VWAP  
5. **Régime** — ATR / ADX / Donchian → NO_TRADE possible  

`_final_decision` : jamais d’inversion LONG↔SHORT par un stage ultérieur.

**Cycle V0 :** **aucun import** dans `pipeline.py`.

---

## 4. Points d’intégration possibles (sans toucher BUY/SELL)

| Surface | Pattern existant | Cycle |
|---------|------------------|-------|
| Route lecture seule | `GET /correlations` | `GET /cycle/{symbol}` |
| Lab study | `regime_study`, event-study | `cycle_study` (après V0) |
| Agent tool | `get_correlations` | `get_cycle_state` |
| Screener field | `market_anomaly` post-pipeline | **plus tard** (V0.1) |
| Context page | RSI/CMF/OBV | teaser cycle (après API stable) |
| Evidence pack | SignalContext versionné | side-car ou bump FEATURE_VERSION |

---

## 5. Risques de régression

- Briser l’ordre des routes (golden `route_order_golden.json`) → monter cycle **en append** comme correlations.
- Étendre `SignalContext` sans bump de version → casser evidence historique.
- Ajouter numpy sans décision produit → rupture posture « stdlib indicators ».
- Brancher trop tôt une gate → faux NO_TRADE / double veto avec ATR/ADX.

---

## 6. Risques de redondance

| Existant | Chevauchement | Décision |
|----------|---------------|----------|
| ATR regime | « marché mort / extrême » | Cycle ≠ ATR ; pas de veto V0 |
| ADX | force de tendance | Régime CYCLE vs TREND peut **compléter** ADX en recherche |
| Donchian | range break | Idem, pas de gate |
| Anomaly z-score | « inhabituel » | Famille différente (événement vs périodicité) |
| PPO/MACD | momentum | Hors cœur ; Cycle ne remplace pas |

---

## 7. Comparaison FFT / Hilbert / ACF / EMD

| Famille | Apporte | Faiblesses | Place IchiVol |
|---------|---------|------------|---------------|
| **FFT / periodogram** | Périodes dominantes, concentration spectrale | Non-stationnarité, leakage, faux cycles, sensibilité fenêtre | V0 EXPERIMENT |
| **Hilbert / Ehlers-style** | Phase, in-phase/quad, trend_mode | Estimation bruitée bar-à-bar | V0 EXPERIMENT |
| **ACF** | Validation périodicité indépendante | Besoin d’historique ; pics faibles en noise | V0 EXPERIMENT |
| **Consensus FFT∩Hilbert∩ACF** | Stabilité / qualité | Pas une proba de gain | V0 EXPERIMENT |
| **EMD / EEMD / CEEMDAN** | IMF, fréquence instantanée | CPU, latence, mode mixing, deps | **LAB ONLY** — REJECT live |
| **TA-Lib HT_*** | Baseline known | Dépendance native absente | REJECT dep ; réimplémenter si besoin |
| **Wickra catalogue** | Inspiration Ehlers | Import massif = salade | REJECT import ; concepts filtrés |
| **fraro01 Fourier Finance** | Pédagogie | Pas une lib prod | REFERENCE only |

---

## 8. Dépendances réellement nécessaires

**État :** `requirements.txt` = FastAPI stack + pytest. **Pas** numpy / scipy / talib / pandas.

**V0 :** stdlib only (DFT / periodogram / ACF / Hilbert approx en Python pur), comme `correlation/engine.py`.

**Plus tard (si benchmark 40–100 symboles échoue) :** numpy candidate **Lab batch only**, décision produit explicite — pas snuck-in.

---

## 9. Risques look-ahead

Interdit :

- FFT sur série entière puis « rejouer » l’historique comme si connu à T  
- Normalisation globale incluant le futur  
- Filtres centrés non causaux  
- Sélection de fréquence optimisée hors-échantillon puis appliquée in-sample sans walk-forward  

Obligatoire :

- À chaque barre T : `data <= T` uniquement  
- Tests truncation (pattern `tests/indicators/test_*_lookahead.py`)  
- Warmup explicite ; early bars → `quality` bas / `NOISE`  
- Projections futures = display-only, labelées non-certaines (hors V0)

---

## 10. Proposition `CycleState`

```text
CycleState {
  dominant_period_candles: float | null
  secondary_period_candles: float | null
  phase: float            # [0, 1) fraction de cycle
  phase_deg: float        # [0, 360)
  amplitude_normalized: float | null
  spectral_power: float | null
  spectral_concentration: float | null
  cycle_strength: float   # [0, 1]
  cycle_stability: float  # [0, 1] stabilité période sur fenêtre récente
  regime: TREND | CYCLE | TRANSITION | NOISE
  bars_to_next_phase: float | null   # estimé ; null si unstable
  quality: float          # [0, 1]
  methods_agreement: float  # accord FFT/Hilbert/ACF — ≠ P(win)
  methods: { fft, hilbert, acf }   # payloads bruts pour debug Lab
}
```

**Jamais :** `buy` / `sell` / `long` / `short` / `probability_win`.

---

## 11. Proposition `CycleStack` (post-V0)

Un `CycleState` par TF (`5m`…`1d`) + `alignment`, `dominant_horizon`, `regime_alignment`, `cycle_structure_quality`.

**ALIGNMENT ≠ probabilité de gain.** Hors V0.

---

## 12. Stratégie Multi-TF

Réutiliser la discipline MTF existante (bougie HTF **fermée** uniquement).  
V0 = **un TF** par appel API. Stack = après mono-TF stable.

---

## 13. Stratégie `ExpectedMoveRange`

Comparer amplitude spectrale vs ATR vs swings Structure / Donchian.  
Calibrer coverage (MAE, interval coverage) en walk-forward.  
**Hors V0** — sinon rectangles arbitraires.

---

## 14. Stratégie Regime Detection

Mapping heuristique V0 (à calibrer) :

| Signaux | Régime |
|---------|--------|
| Forte tendance Hilbert trend_mode + faible concentration spectrale | TREND |
| Accord méthodes + force/stabilité élevés | CYCLE |
| Désaccord méthodes / période qui saute | TRANSITION |
| Qualité basse / pas de pic ACF | NOISE |

**Hypothèse produit à tester :** filtre de régime **>** prédicteur de prix.

---

## 15. Protocole walk-forward

```
pour T in [warmup .. N-horizon]:
  state = CycleState(candles[:T+1])   # causal
  pred  = derive(state)               # phase/horizon/range si activé
  score vs candles[T+1 : T+1+n]
  avancer T+1
```

Pas de mélange train/test ; pas de retuning sur la fenêtre de score.

---

## 16. Ablation study (à instrumenter au Lab)

| ID | Config |
|----|--------|
| A | IchiVol actuel |
| B | + FFT alone (observe) |
| C | + Hilbert alone |
| D | + ACF alone |
| E | FFT + Hilbert |
| F | FFT + Hilbert + ACF |
| G | Cycle complet (post-V0 stack/range) |

Métriques trade **et** métriques cycle (stability, phase error, false-cycle rate, regime accuracy).

---

## 17. Null models

- Random phase / random horizon  
- Historical average cycle  
- ATR-only range  
- Naive momentum  
- Previous-cycle persistence  

Si V0 ne bat pas ces baselines OOS → **ne pas** intégrer au moteur de décision.

---

## 18. Benchmark performance (mesuré 2026-09-26)

Synthetic sine, `window=128`, `bars=300`, avant optimisation API :

| Charge | ms / symbole (mean) | Note |
|--------|---------------------|------|
| 1 | ~5400 | `compute_cycle_state` recalculait toute la série |
| 40 | ~7500 | Inutilisable en screener live |
| 100 | ~7600 | Idem |

**Correctif V0.1** : `compute_cycle_state` ne calcule que les `stability_lookback` dernières fenêtres (API/agent). `compute_cycle_series` reste pour Lab walk-forward (volontairement plus cher).

**Re-mesure après fix (même machine, synthétique)** : ~620 ms / symbole (1) · ~730 ms / symbole (×10) — ~9× plus rapide. Acceptable pour appel à la demande ; screener 40–100 toujours hors scope.

Hypothèse : FFT/Hilbert/ACF → candidats live **après** perf ; EMD → Lab. **À vérifier.**

---

## 19. Fichiers qui seraient créés (V0)

```
docs/CYCLE_ENGINE_AUDIT.md          (ce fichier)
ichivol-app/engine/app/cycle/__init__.py
ichivol-app/engine/app/cycle/types.py
ichivol-app/engine/app/cycle/preprocess.py
ichivol-app/engine/app/cycle/fft.py
ichivol-app/engine/app/cycle/hilbert.py
ichivol-app/engine/app/cycle/acf.py
ichivol-app/engine/app/cycle/consensus.py
ichivol-app/engine/app/cycle/engine.py
ichivol-app/engine/app/api/cycle.py
ichivol-app/engine/tests/cycle/...
```

---

## 20. Fichiers qui seraient modifiés (V0)

```
docs/CAHIER-DES-CHARGES.md
docs/METHODS-ROADMAP.md
docs/HANDOFF-CURSOR-V3.md
ichivol-app/engine/app/api/routes.py
ichivol-app/engine/README.md
(+ golden route_order si exigé par tests)
```

**Interdit V0 :** `decision/pipeline.py`, paper broker, combiner, confidence.

---

## GO / EXPERIMENT / REJECT

| Méthode | Verdict | Justification |
|---------|---------|---------------|
| FFT periodogram causal | **EXPERIMENT** | Période dominante ; faux cycles à filtrer via qualité |
| Hilbert / Ehlers period+phase | **EXPERIMENT** | Phase / trend_mode — cœur « où dans le cycle » |
| ACF peaks | **EXPERIMENT** | Validation croisée indépendante |
| Consensus multi-méthodes | **EXPERIMENT** | Accord+stabilité ≠ P(win) |
| Régime comme **filtre** recherche | **EXPERIMENT** | Priorité produit vs prédire T+1 |
| ExpectedMoveRange / zones | **RESEARCH** | Après calibration |
| CycleStack MTF | **RESEARCH** | Après mono-TF |
| EMD/EEMD/CEEMDAN live | **REJECT** | Coût / stabilité ; Lab only si un jour |
| TA-Lib / Wickra deps | **REJECT** | Hors posture deps |
| Vote BUY/SELL Cycle | **REJECT** | Jusqu’à preuve OOS |

---

## Matrice information incrémentale (draft)

| Indicateur | Famille | Action |
|------------|---------|--------|
| Ichimoku | Trend | KEEP |
| RVOL | Volume anomaly | KEEP |
| Structure | Price structure | KEEP |
| ATR | Volatility | KEEP |
| ADX | Trend strength | KEEP |
| RSI/CMF/OBV | Oscillator / flow | RESEARCH (paper) |
| FFT | Frequency | **EXPERIMENT** |
| Hilbert | Cycle phase | **EXPERIMENT** |
| ACF | Periodicity | **EXPERIMENT** |
| EMD | Mode decomposition | REJECT live |

---

## Claude Agent

Python calcule `CycleState`. Claude reçoit JSON structuré et **interprète** — n’invente pas de projection ni de BUY.

---

## Prochaines étapes ordonnées

1. ~~Audit (ce doc)~~  
2. ~~Inscription CDC / METHODS / HANDOFF~~  
3. ~~Package `app/cycle` + tests lookahead~~  
4. ~~Route `GET /cycle/{symbol}`~~  
5. ~~Walk-forward + null models (`study.py`) + agent tools + benchmark helper~~  
6. **Suite** : multi-symbol OOS réel, ablation A–G, benchmark 40/100 candles live, décision filtre vs prédicteur — **avant toute gate**  
