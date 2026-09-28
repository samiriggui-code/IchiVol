# VP-S1 — notes d'implémentation (étape 1, aucun run)

## S1-R1 (code) — BM horizon 90 j + `force_flat`

- Après la fin de pli, BM simule encore **90 jours calendaires**, puis `force_flat_at_end` avec raison **`horizon_end`**.
- Ces sorties entrent dans `trades` (et donc `n_trades` / espérance). L'equity reportée reste coupée au pli (S1–S4 inchangés).
- `strategy_rules("BM")` garde `force_flat_at_end=False` ; c'est `vp3/wf.run_fold` qui active le flat + raison.
- **Plafond dev (revue Claude 2026-09-28)** : sur les plis WF, l'horizon BM est coupé à `DEV_END_EXCL_S` = 2025-01-01 00:00 UTC (`vp3/wf.sim_end_s`). Sans ce plafond, WF7 (fin 2024-12-31) lisait les prix de janvier à mars 2025, donc la validation. Pour WF7, le `force_flat` `horizon_end` a donc lieu à la dernière barre de 2024. Test : `test_bm_horizon_never_reads_validation_2025`.
- Les autres stratégies gardent l'horizon VP3-R3 figé (inchangé, runs antérieurs reproductibles). Note : pour WF7, cet horizon de 48 barres déborde déjà de 2 jours (1h) ou 8 jours (4h) sur 2025 pour les sorties. C'est un débordement préexistant, hors périmètre, signalé ici.

## S1-R2 (doc seulement) — deux définitions de maxDD

| Lieu | Définition |
|------|------------|
| **S1** | Pire maxDD **par pli** (parmi les 7 plis WF). |
| **S4** | maxDD sur la série **concaténée** des returns par barre des 7 plis, rééchantillonnée par **blocs ~24 barres** (`paired_block_delta_ci`). |

Conséquence : le bootstrap S4 peut **sous-estimer** le maxDD de B0 si un krach long est découpé en blocs. Le Δ BM−B0 reste **apparié** (même découpage) donc interprétable, mais **n'est pas** le même objet que le maxDD S1.

Pas de changement de code (amendement : « returns par barre »).

## INFO

Le live peut ré-entrer dans une même série après redémarrage (audit VP-P) ; BM applique « une entrée par série » en continu. Pas de changement (BM figé).
