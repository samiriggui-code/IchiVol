# Étude T12e — ADN IchiVol (matrice A→F)

**Statut** : module Lab livré ; matrice crypto deep_history ≥2 ans **partiellement exécutable** (voir §6 couverture).  
**Observation only** — aucun changement live (decision / screener / paper / brokerage).  
**Code** : `ichivol-app/engine/app/strategy_lab/adn_ichivol.py`  
**Critères** : T9g-fix (`decide_recommendation`) → KEEP / RESEARCH / REJECT.

---

## 0. Réponse courte

| Couche | Rôle | Verdict provisoire (synthétique + méthode) |
|--------|------|--------------------------------------------|
| A Ichimoku | Baseline ADN | **RESEARCH** (besoin OOS ≥2 ans crypto) |
| B +RVOL | A + `rvol_min` = settings live | **RESEARCH** jusqu’à ablation_oos deep_history |
| C Structure+RVOL | Parallèle (sans Ichimoku) | **RESEARCH** |
| D Ichi+Struct+RVOL | Cumulatif | **RESEARCH** |
| E +Location | `location_stage_pass=pass` | **RESEARCH** |
| F +Régime | `regime_stage_pass=pass` | **RESEARCH** |
| IchiVol actuel | Catalog `IV_ICHIMOKU_RVOL_LONG_001` | **RESEARCH** (réf. étude 2026-09-20 : net négatif) |
| Refs T12c | buy&hold / Donchian / BOS | disponibles via `run_reference_baselines_on_candles` |

**Aucun KEEP** tant que la matrice deep_history crypto 1h/4h/1d ≥2 ans n’a pas tourné avec les paramètres screener live et frais base+adverse.  
**Aucun changement live recommandé** (arrêt obligatoire rév.58).

---

## 1. Définition des modèles

### Ladder cumulative (ablation OOS additive)

| Label | Conditions ajoutées |
|-------|---------------------|
| A_ICHIMOKU | `price_above_kumo`, `tenkan_above_kijun`, `tk_cross_age_max=3` |
| B_RVOL | `rvol_min` = **LiveScreenerSettings.rvol_significant** (défaut prod 1.5) |
| D_STRUCTURE | `bos_bullish` |
| E_LOCATION | `location_stage_pass=pass` |
| F_REGIME | `regime_stage_pass=pass` |

### Parallèle

| Label | Conditions |
|-------|------------|
| C_STRUCT_RVOL | `bos_bullish` + `rvol_min` (sans Ichimoku) |

### Paramètres « screener live »

**DÉCISION CURSOR — à relire par Claude** : snapshot figé = défauts `server/src/settings/resolve.ts` (`LiveScreenerSettings.production_defaults`). Injection possible via `LiveScreenerSettings.from_mapping(...)` (clés UI camelCase). Ce n’est **pas** le `rvol_min=1.5` hardcodé de l’ancienne ladder `default` seule — la source est nommée dans le rapport (`settings.source`).

Frais (T9g) : base 5+3 bps ; adverse 10+8 bps.

---

## 2. Mapping verdicts T9g-fix

| `recommendation` | Verdict étude |
|------------------|---------------|
| `review_candidate` | **KEEP** |
| `inconclusive` | **RESEARCH** |
| `reject` | **REJECT** |

KEEP ≠ promotion FeatureStatus (T10e / humain).

Compteur T10b : `hypothesis_id=t12e_adn_{symbol}_{timeframe}` → `lineage_trial_count` sur le rapport ablation_oos.

---

## 3. Grille cible (à remplir après runs deep_history)

Symboles crypto prioritaires : BTCUSDT, ETHUSDT (± SOLUSDT).  
Horizons : 1h, 4h, 1d. Fenêtre : ≥ 2 ans (`resolve_lab_history(..., deep_history=True, years=2.0)`).

### Template — modèle × actif × horizon

| Modèle | Actif | TF | n_bars | OOS Δ exp | Adverse Δ | trades OOS | Verdict |
|--------|-------|-----|--------|-----------|-----------|------------|---------|
| A | BTCUSDT | 1h | — | — | — | — | RESEARCH |
| B | BTCUSDT | 1h | — | — | — | — | RESEARCH |
| C | BTCUSDT | 1h | — | — | — | — | RESEARCH |
| D | BTCUSDT | 1h | — | — | — | — | RESEARCH |
| E | BTCUSDT | 1h | — | — | — | — | RESEARCH |
| F | BTCUSDT | 1h | — | — | — | — | RESEARCH |
| ICHIVOL | BTCUSDT | 1h | — | — | — | — | RESEARCH |
| REF_BH | BTCUSDT | 1h | — | — | — | — | (ref) |
| REF_DON | BTCUSDT | 1h | — | — | — | — | (ref) |
| REF_BOS | BTCUSDT | 1h | — | — | — | — | (ref) |

*(Répéter pour ETH × {1h,4h,1d}.)*

### Régimes

Trancher via `run_regime_slices_on_candles` **après** le premier passage ablation_oos (même série). Colonnes prévues : trending / ranging × ADX ; ne pas inventer de chiffres ici.

---

## 4. API d’exécution

```python
from app.strategy_lab.adn_ichivol import (
    LiveScreenerSettings,
    run_adn_matrix_on_candles,
)
from app.strategy_lab.deep_history import resolve_lab_history

settings = LiveScreenerSettings.production_defaults()  # ou from_mapping(api_settings)
bundle = resolve_lab_history("BTCUSDT", "1h", deep_history=True, years=2.0)
report = run_adn_matrix_on_candles(
    bundle.candles,
    symbol="BTCUSDT",
    timeframe="1h",
    settings=settings,
    hypothesis_id="t12e_adn_BTCUSDT_1h",
    coverage_note=bundle.history_warning,
)
# report.rows[*].verdict ∈ {KEEP, RESEARCH, REJECT}
```

Ladder HTTP : `ladder="adn_ichivol"` (enregistrée dans `ABLATION_LADDERS`).

Script : `ichivol-app/engine/scripts/t12e_adn_study.py` (si présent).

---

## 5. Correctif annexe (T12e)

`ruleset._coerce_leaf` : enums `location_stage_pass` / `regime_stage_pass` (valeurs minuscules FeatureBar) étaient **inutilisables** car la coercition forçait `UPPER` hors de l’ensemble autorisé. Fix case-insensitive → forme canonique. Sans ce fix, E/F ADN ne parseaient pas.

---

## 6. Couverture données (environnement agent)

| Classe | ≥2 ans 1h/4h/1d | Note |
|--------|-----------------|------|
| Crypto Binance | Oui (API) | Dans cet environnement cloud : **HTTP 451** vers `api.binance.com` → deep_history live **bloqué ici**. Relancer sur VPS / machine avec accès Binance ; datasets cache `strategy_lab/datasets/`. |
| Forex / métaux / equities | Non (plafond Twelve Data ~5k barres) | **1h ≪ 2 ans** — **hors matrice T12e** ; documenté, pas de faux 2 ans. |

Tests unitaires : série synthétique 320 barres (`test_t12e_adn_ichivol.py`) — valident wiring, settings override, verdicts, refs T12c ; **pas** les verdicts économiques.

---

## 7. Hors scope / ne pas faire

- Modifier seuils live, FeatureStatus, kill switch, promote auto  
- Remplacer la ladder `default` historique (A–E CMF) — ADN est une ladder **add-only** `adn_ichivol`  
- Forex/actions dans le tableau KEEP tant que couverture insuffisante  

---

## 8. Suite recommandée (humain / VPS)

1. Exporter settings live réels → `LiveScreenerSettings.from_mapping`  
2. `resolve_lab_history` BTC+ETH × 1h/4h/1d × years=2  
3. Remplir §3 + tranches régime  
4. Claude + user : seuls KEEP éventuels → fiche T10d / critères T10e  

SHA / PR : voir handoff Cursor (entrée T12e).
