# T10d — Candidat `cmf`

| Champ | Valeur |
|-------|--------|
| **id** | `cmf` |
| **Nom** | Chaikin Money Flow |
| **Status** | `CANDIDATE` |
| **Famille** | flux |
| **Source** | internal (`app/indicators/cmf.py`) |
| **confirmation_lag_bars** | 0 |
| **hypothesis_id** (convention) | `t10d_cmf` |

---

## 1. Hypothèse

Le CMF agrège pression acheteuse/vendeuse via volume × position dans la range. Utile comme **filtre de participation / flux** en Lab (couche d’ablation type `E_CMF` dans certains profils), en complément — pas en remplacement — de RVOL et CVD.

**Ne doit pas** (CANDIDATE) :
- voter dans le combiner live
- être traité comme volume d’exchange sur séries tick-volume (biquote) sans `volume_type` explicite

---

## 2. Provenance code

- Compute : `REGISTRY` id `cmf` → `compute_cmf` / `CmfParams`
- API context : panneau context
- Lab : couche d’ablation / FeatureBar quand présente
- Sens volume : dépend de `Candle.volume_type` (T11a)

---

## 3. Preuves (à compléter)

| Étude | hypothesis_id | n_bars | reco T9g | Notes |
|-------|---------------|--------|----------|-------|
| — | `t10d_cmf` | — | — | Mesurer vs CVD avant toute promo |

---

## 4. Redondance (T10c) — critique

| Pair | Risque | Commentaire |
|------|--------|-------------|
| **CMF vs CVD** | **Élevé** | Même famille flux ; CMF ne doit pas être PRODUCTION s’il n’apporte rien après CVD + RVOL |
| CMF vs OBV | Moyen | OBV cumulatif vs CMF borné |

Toute PR PRODUCTION exige un résultat T10c / ablation montrant une **valeur marginale** claire.

---

## 5. Décision

| Proposition | Owner | Date |
|-------------|-------|------|
| Rester **CANDIDATE** ; priorité à l’étude de redondance vs CVD | Claude + user | 2026-09-24 |

---

## 6. Non-goals

- Promotion sans T10c écrit
- Usage sur `volume_type=TICK_VOLUME` présenté comme exchange volume
- Auto-promote / wiring pipeline silencieux
