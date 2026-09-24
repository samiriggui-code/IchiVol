# T10d — Candidat `rsi`

| Champ | Valeur |
|-------|--------|
| **id** | `rsi` |
| **Nom** | Relative Strength Index |
| **Status** | `CANDIDATE` |
| **Famille** | momentum |
| **Source** | internal (`app/indicators/rsi.py`) |
| **confirmation_lag_bars** | 0 |
| **hypothesis_id** (convention) | `t10d_rsi` |

---

## 1. Hypothèse

RSI mesure l’excès de momentum sur une fenêtre courte. En tant que **filtre Lab / panneau context**, il peut étiqueter zones surachetées / survendues **sans** voter BUY/SELL dans le combiner.

**Ne doit pas** (tant que CANDIDATE) :
- entrer dans `decision/pipeline` ou `combiner`
- remplacer Ichimoku pour la direction

---

## 2. Provenance code

- Compute : `REGISTRY` id `rsi` → `compute_rsi` / `RsiParams`
- API context : exposé via routes context (panneau)
- Lab : conditions `rsi_min` / `rsi_max` (FeatureBar) quand branchées
- Tests lookahead : suite registry / indicateurs

Params par défaut : voir `RsiParams` (période standard 14 sauf override Lab).

---

## 3. Preuves (à compléter)

| Étude | hypothesis_id | n_bars | reco T9g | Notes |
|-------|---------------|--------|----------|-------|
| — | `t10d_rsi` | — | — | Aucune ablation_oos dédiée RSI seule à ce jour |

T10b `lineage_trial_count` : compter les expériences Perf DB taguées `t10d_rsi*`.

---

## 4. Redondance (T10c)

| Pair | Risque | Commentaire |
|------|--------|-------------|
| RSI vs ADX | Faible | ADX = régime de tendance ; RSI = vitesse relative |
| RSI vs Ichimoku TK | Moyen | Les deux parlent momentum ; RSI ne doit pas doubler la direction |

---

## 5. Décision

| Proposition | Owner | Date |
|-------------|-------|------|
| Rester **CANDIDATE** jusqu’à étude OOS + revue redondance | Claude + user | 2026-09-24 |

**Prochaine action** : run Lab (filtre `rsi_min`/`rsi_max` sur ruleset de référence) → T9g-fix → mettre à jour ce tableau.

---

## 6. Non-goals

- Auto-promote
- Import pipeline tant que status ≠ PRODUCTION (garde T11a-bis)
- Changement de seuils live
