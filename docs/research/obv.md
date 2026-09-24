# T10d — Candidat `obv`

| Champ | Valeur |
|-------|--------|
| **id** | `obv` |
| **Nom** | On-Balance Volume |
| **Status** | `CANDIDATE` |
| **Famille** | flux |
| **Source** | internal (`app/indicators/obv.py`) |
| **confirmation_lag_bars** | 0 |
| **hypothesis_id** (convention) | `t10d_obv` |

---

## 1. Hypothèse

L’OBV cumule ±volume selon le sens de la clôture. En **context / Lab**, il peut illustrer divergences prix–volume. Il n’est **pas** un filtre Lab conditioné aussi largement que CMF aujourd’hui.

**Ne doit pas** (CANDIDATE) :
- entrer dans le chemin décision live
- être interprété sans `volume_type` (tick vs exchange)

---

## 2. Provenance code

- Compute : `REGISTRY` id `obv` → `compute_obv` / `ObvParams`
- API context : panneau context
- Lab : pas de clés condition aussi riches que CMF/RSI à ce stade — documenter avant d’élargir

---

## 3. Preuves (à compléter)

| Étude | hypothesis_id | n_bars | reco T9g | Notes |
|-------|---------------|--------|----------|-------|
| — | `t10d_obv` | — | — | Besoin d’une ruleset Lab dédiée avant T9g |

---

## 4. Redondance (T10c)

| Pair | Risque | Commentaire |
|------|--------|-------------|
| OBV vs CVD | Élevé | Divergence vs flux signé ; clarifier cas d’usage |
| OBV vs CMF | Moyen | Cumul vs oscillateur borné |
| OBV vs RVOL | Faible | RVOL = intensité relative bar ; OBV = cumul |

---

## 5. Décision

| Proposition | Owner | Date |
|-------------|-------|------|
| Rester **CANDIDATE** ; d’abord définir condition Lab + étude OOS | Claude + user | 2026-09-24 |

---

## 6. Non-goals

- PRODUCTION sans fiche + T9g + redondance
- Auto-promote
- Import pipeline (garde T11a-bis)
