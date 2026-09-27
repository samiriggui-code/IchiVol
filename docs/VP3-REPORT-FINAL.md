# VP3 — rapport FINAL (VP-J1)

**Job :** VP-J1 étape 2 · branche `cursor/vp-j1-a2fe`
**Protocole :** `VP0-2026-09-26` · **N T10b gelé = 36**
**Coûts :** base + adverse · **n_boot :** 10 000
**DSR :** σ(SR_ann) sur 36 hyps → SR*_ann → PSR à l’échelle **barre** (`dsr_bar_scaled`)
**Questions :** A / B / H / **J** (Bj = argmax DSR parmi B0–B6, tie → plus simple)
**B6/B7 :** live ATR+ADX gate + `WARMUP_BARS` (fixes pré-run)
**Time-stop :** VP2-R1 · **Date run :** 2026-09-27

> Artefact JSON : [`docs/vp3-artifacts/j1_results.json`](./vp3-artifacts/j1_results.json).

### Conclusion

**0 EDGE / 48** cases (24 base + 24 adverse). SR*_ann = **0.935** (base) / **1.27** (adverse). Meilleur DSR_i = **0.506** (B0 · SOLUSDT 4h · 7 trades). Bj map base : BTCUSDT 1h=B6, BTCUSDT 4h=B5, ETHUSDT 1h=B0, ETHUSDT 4h=B0, SOLUSDT 1h=B0, SOLUSDT 4h=B0.

## σ / SR* (N=36)

| Profil | σ(SR_ann) | SR*_ann | SR*_bar 1h | SR*_bar 4h |
|---|---:|---:|---:|---:|
| base | 0.631348 | 0.934892 | 0.00998871 | 0.0199774 |
| adverse | 0.857545 | 1.26984 | 0.0135674 | 0.0271349 |

## Bj (base → adverse)

| symbole | TF | Bj |
|---|---|---|
| BTCUSDT | 1h | B6 |
| BTCUSDT | 4h | B5 |
| ETHUSDT | 1h | B0 |
| ETHUSDT | 4h | B0 |
| SOLUSDT | 1h | B0 |
| SOLUSDT | 4h | B0 |

## 36 SR_ann (base + adverse)

| B* | symbole | TF | SR_ann base | DSR base | SR_ann adverse | DSR adverse | N trades base |
|---|---|---|---:|---:|---:|---:|---:|
| B0 | BTCUSDT | 1h | 0.7766 | 0.3835 | 0.7723 | 0.1759 | 7 |
| B0 | BTCUSDT | 4h | 0.8198 | 0.4147 | 0.8153 | 0.1975 | 7 |
| B0 | ETHUSDT | 1h | 0.496 | 0.2057 | 0.4926 | 0.07289 | 7 |
| B0 | ETHUSDT | 4h | 0.5093 | 0.213 | 0.5058 | 0.07644 | 7 |
| B0 | SOLUSDT | 1h | 0.927 | 0.4941 | 0.9248 | 0.2589 | 7 |
| B0 | SOLUSDT | 4h | 0.9424 | 0.5056 | 0.9402 | 0.2679 | 7 |
| B1 | BTCUSDT | 1h | -1.066 | 9.629e-05 | -2.259 | 2.262e-11 | 317 |
| B1 | BTCUSDT | 4h | 0.2783 | 0.1071 | -0.06594 | 0.006301 | 71 |
| B1 | ETHUSDT | 1h | -1.075 | 8.560e-05 | -2.079 | 1.601e-10 | 296 |
| B1 | ETHUSDT | 4h | -0.3735 | 0.007301 | -0.6478 | 1.731e-04 | 76 |
| B1 | SOLUSDT | 1h | 0.8162 | 0.4114 | 0.2477 | 0.02757 | 265 |
| B1 | SOLUSDT | 4h | 0.6057 | 0.268 | 0.4525 | 0.06259 | 68 |
| B2 | BTCUSDT | 1h | -0.1189 | 0.02437 | -0.8773 | 3.001e-05 | 129 |
| B2 | BTCUSDT | 4h | 0.5433 | 0.2251 | 0.3325 | 0.03739 | 22 |
| B2 | ETHUSDT | 1h | -0.1066 | 0.02562 | -0.7945 | 5.311e-05 | 119 |
| B2 | ETHUSDT | 4h | -0.7409 | 7.780e-04 | -0.8737 | 2.330e-05 | 21 |
| B2 | SOLUSDT | 1h | 0.8211 | 0.4145 | 0.4483 | 0.06081 | 98 |
| B2 | SOLUSDT | 4h | 0.8845 | 0.4615 | 0.7884 | 0.1793 | 26 |
| B5 | BTCUSDT | 1h | 0.1854 | 0.07994 | -0.5039 | 4.514e-04 | 99 |
| B5 | BTCUSDT | 4h | 0.8361 | 0.4229 | 0.6618 | 0.1198 | 14 |
| B5 | ETHUSDT | 1h | -0.02123 | 0.03673 | -0.6055 | 2.131e-04 | 91 |
| B5 | ETHUSDT | 4h | -0.71 | 9.056e-04 | -0.8203 | 3.322e-05 | 17 |
| B5 | SOLUSDT | 1h | 0.6583 | 0.2995 | 0.3175 | 0.03636 | 80 |
| B5 | SOLUSDT | 4h | 0.3951 | 0.154 | 0.3156 | 0.03619 | 17 |
| B6 | BTCUSDT | 1h | 0.9385 | 0.5027 | 0.5988 | 0.1049 | 23 |
| B6 | BTCUSDT | 4h | -0.2966 | 0.01072 | -0.3724 | 0.001009 | 3 |
| B6 | ETHUSDT | 1h | 0.3475 | 0.1373 | 0.1314 | 0.0169 | 19 |
| B6 | ETHUSDT | 4h | -0.4025 | 0.004018 | -0.4404 | 3.172e-04 | 3 |
| B6 | SOLUSDT | 1h | -0.08984 | 0.02788 | -0.2715 | 0.00205 | 13 |
| B6 | SOLUSDT | 4h | 0.06709 | 0.05044 | 0.02469 | 0.009677 | 5 |
| B7 | BTCUSDT | 1h | -1.052 | 1.294e-04 | -2.054 | 5.422e-10 | 205 |
| B7 | BTCUSDT | 4h | -0.06454 | 0.0307 | -0.4217 | 7.552e-04 | 67 |
| B7 | ETHUSDT | 1h | -0.362 | 0.007714 | -1.145 | 3.279e-06 | 210 |
| B7 | ETHUSDT | 4h | 0.3286 | 0.1279 | 0.09146 | 0.0137 | 53 |
| B7 | SOLUSDT | 1h | -0.874 | 3.834e-04 | -1.343 | 6.044e-07 | 191 |
| B7 | SOLUSDT | 4h | 0.2461 | 0.09728 | 0.09341 | 0.01367 | 62 |

## Compares — profil **base**

| Q | Symbole | TF | Bj | Δmean | IC Δ | IC trades Bi | DSR_i | +plis | N | maxDD | beats | verdict | verdict_final |
|---|---|---|---|---:|---|---|---:|---:|---:|---:|---|---|---|
| A | BTCUSDT | 1h | B0 | -7.037e-05 | [-1.321e-04, -6.120e-06] excl.0 | [-38.67, -1.608] excl.0 | 9.629e-05 | 2/7 | 317 | -0.2683 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | BTCUSDT | 1h | B1 | 1.993e-05 | [4.274e-06, 3.548e-05] excl.0 | [-32.95, 25.78] ∋0 | 0.02437 | 3/7 | 129 | -0.1323 | False | PAS D'EDGE | **PAS D'EDGE** |
| H | BTCUSDT | 1h | B2 | 3.614e-06 | [-2.230e-06, 9.737e-06] ∋0 | [-27.13, 39.81] ∋0 | 0.07994 | 3/7 | 99 | -0.1203 | False | NON CONCLUANT | **NON CONCLUANT** |
| J | BTCUSDT | 1h | B6 | -2.108e-05 | [-3.628e-05, -5.645e-06] excl.0 | [-44.94, 0.924] ∋0 | 1.294e-04 | 2/7 | 205 | -0.1669 | False | PAS D'EDGE | **PAS D'EDGE** |
| A | BTCUSDT | 4h | B0 | -1.853e-04 | [-4.333e-04, 6.881e-05] ∋0 | [-53.48, 106.4] ∋0 | 0.1071 | 3/7 | 71 | -0.2226 | False | NON CONCLUANT | **NON CONCLUANT** |
| B | BTCUSDT | 4h | B1 | -8.131e-08 | [-6.068e-05, 5.754e-05] ∋0 | [-58.84, 191.2] ∋0 | 0.2251 | 0/7 | 22 | -0.127 | False | NON CONCLUANT | **NON CONCLUANT** |
| H | BTCUSDT | 4h | B2 | 3.213e-06 | [-1.979e-05, 2.496e-05] ∋0 | [-35.57, 264] ∋0 | 0.4229 | 0/7 | 14 | -0.03434 | False | NON CONCLUANT | **NON CONCLUANT** |
| J | BTCUSDT | 4h | B5 | -2.474e-05 | [-8.808e-05, 3.988e-05] ∋0 | [-76.59, 70.07] ∋0 | 0.0307 | 4/7 | 67 | -0.1529 | False | NON CONCLUANT | **NON CONCLUANT** |
| A | ETHUSDT | 1h | B0 | -6.302e-05 | [-1.410e-04, 1.753e-05] ∋0 | [-46.66, -0.6612] excl.0 | 8.560e-05 | 1/7 | 296 | -0.2578 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | ETHUSDT | 1h | B1 | 2.250e-05 | [4.316e-06, 4.088e-05] excl.0 | [-39.69, 33.38] ∋0 | 0.02562 | 3/7 | 119 | -0.1274 | False | PAS D'EDGE | **PAS D'EDGE** |
| H | ETHUSDT | 1h | B2 | 1.160e-06 | [-4.673e-06, 6.964e-06] ∋0 | [-42.48, 41.87] ∋0 | 0.03673 | 2/7 | 91 | -0.1132 | False | PAS D'EDGE | **PAS D'EDGE** |
| J | ETHUSDT | 1h | B0 | -4.658e-05 | [-1.263e-04, 3.493e-05] ∋0 | [-41.41, 18.75] ∋0 | 7.714e-03 | 2/7 | 210 | -0.2316 | False | PAS D'EDGE | **PAS D'EDGE** |
| A | ETHUSDT | 4h | B0 | -1.900e-04 | [-4.998e-04, 1.311e-04] ∋0 | [-119.5, 50] ∋0 | 7.301e-03 | 2/7 | 76 | -0.1916 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | ETHUSDT | 4h | B1 | -2.634e-06 | [-7.374e-05, 6.700e-05] ∋0 | [-261.6, 26.78] ∋0 | 7.780e-04 | 1/7 | 21 | -0.1472 | False | NON CONCLUANT | **NON CONCLUANT** |
| H | ETHUSDT | 4h | B2 | 2.532e-06 | [-1.798e-05, 2.005e-05] ∋0 | [-285.4, 17.12] ∋0 | 9.056e-04 | 1/7 | 17 | -0.09156 | False | NON CONCLUANT | **NON CONCLUANT** |
| J | ETHUSDT | 4h | B0 | -1.353e-04 | [-4.487e-04, 1.850e-04] ∋0 | [-77.07, 144.8] ∋0 | 0.1279 | 5/7 | 53 | -0.1862 | False | PAS D'EDGE | **PAS D'EDGE** |
| A | SOLUSDT | 1h | B0 | -8.583e-05 | [-2.067e-04, 3.545e-05] ∋0 | [-17.56, 87.74] ∋0 | 0.4114 | 4/7 | 265 | -0.273 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | SOLUSDT | 1h | B1 | -1.280e-05 | [-4.459e-05, 1.822e-05] ∋0 | [-17.09, 123.3] ∋0 | 0.4145 | 4/7 | 98 | -0.1645 | False | PAS D'EDGE | **PAS D'EDGE** |
| H | SOLUSDT | 1h | B2 | -4.796e-06 | [-1.668e-05, 5.108e-06] ∋0 | [-28.4, 118.2] ∋0 | 0.2995 | 5/7 | 80 | -0.1291 | False | PAS D'EDGE | **PAS D'EDGE** |
| J | SOLUSDT | 1h | B0 | -1.427e-04 | [-2.679e-04, -1.883e-05] excl.0 | [-88.55, 0.2809] ∋0 | 3.834e-04 | 0/7 | 191 | -0.3258 | False | PAS D'EDGE | **PAS D'EDGE** |
| A | SOLUSDT | 4h | B0 | -3.723e-04 | [-8.615e-04, 1.208e-04] ∋0 | [-97.48, 276.3] ∋0 | 0.268 | 4/7 | 68 | -0.2593 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | SOLUSDT | 4h | B1 | -9.180e-06 | [-1.191e-04, 9.847e-05] ∋0 | [-109.3, 540.5] ∋0 | 0.4615 | 2/7 | 26 | -0.1589 | False | NON CONCLUANT | **NON CONCLUANT** |
| H | SOLUSDT | 4h | B2 | -4.838e-05 | [-1.097e-04, 6.409e-06] ∋0 | [-290.7, 513.5] ∋0 | 0.154 | 0/7 | 17 | -0.1589 | False | NON CONCLUANT | **NON CONCLUANT** |
| J | SOLUSDT | 4h | B0 | -4.251e-04 | [-9.065e-04, 7.162e-05] ∋0 | [-151.6, 215.6] ∋0 | 0.09728 | 3/7 | 62 | -0.2287 | False | NON CONCLUANT | **NON CONCLUANT** |

## Compares — profil **adverse**

| Q | Symbole | TF | Bj | Δmean | IC Δ | IC trades Bi | DSR_i | +plis | N | maxDD | beats | verdict | verdict_final |
|---|---|---|---|---:|---|---|---:|---:|---:|---:|---|---|---|
| A | BTCUSDT | 1h | B0 | -9.482e-05 | [-1.570e-04, -3.002e-05] excl.0 | [-58.55, -23.23] excl.0 | 2.262e-11 | 0/7 | 317 | -0.3244 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | BTCUSDT | 1h | B1 | 3.459e-05 | [1.849e-05, 5.064e-05] excl.0 | [-55.56, 1.921] ∋0 | 3.001e-05 | 2/7 | 129 | -0.1677 | False | PAS D'EDGE | **PAS D'EDGE** |
| H | BTCUSDT | 1h | B2 | 5.953e-06 | [-4.910e-08, 1.231e-05] ∋0 | [-50.41, 15.6] ∋0 | 4.514e-04 | 3/7 | 99 | -0.1569 | False | PAS D'EDGE | **PAS D'EDGE** |
| J | BTCUSDT | 1h | B6 | -3.522e-05 | [-5.091e-05, -1.950e-05] excl.0 | [-65.87, -21.37] excl.0 | 5.422e-10 | 1/7 | 205 | -0.2285 | False | PAS D'EDGE | **PAS D'EDGE** |
| A | BTCUSDT | 4h | B0 | -2.063e-04 | [-4.548e-04, 4.869e-05] ∋0 | [-76.32, 81.53] ∋0 | 6.301e-03 | 3/7 | 71 | -0.2428 | False | NON CONCLUANT | **NON CONCLUANT** |
| B | BTCUSDT | 4h | B1 | 1.521e-05 | [-4.571e-05, 7.349e-05] ∋0 | [-82.05, 166.3] ∋0 | 0.03739 | 0/7 | 22 | -0.1384 | False | NON CONCLUANT | **NON CONCLUANT** |
| H | BTCUSDT | 4h | B2 | 5.706e-06 | [-1.707e-05, 2.787e-05] ∋0 | [-59.51, 239] ∋0 | 0.1198 | 0/7 | 14 | -0.03448 | False | NON CONCLUANT | **NON CONCLUANT** |
| J | BTCUSDT | 4h | B5 | -4.121e-05 | [-1.051e-04, 2.329e-05] ∋0 | [-99.49, 45.14] ∋0 | 7.552e-04 | 3/7 | 67 | -0.1657 | False | PAS D'EDGE | **PAS D'EDGE** |
| A | ETHUSDT | 1h | B0 | -8.578e-05 | [-1.642e-04, -4.463e-06] excl.0 | [-66.16, -22.02] excl.0 | 1.601e-10 | 1/7 | 296 | -0.3151 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | ETHUSDT | 1h | B1 | 3.624e-05 | [1.776e-05, 5.516e-05] excl.0 | [-62.48, 9.405] ∋0 | 5.311e-05 | 2/7 | 119 | -0.1471 | False | PAS D'EDGE | **PAS D'EDGE** |
| H | ETHUSDT | 1h | B2 | 3.341e-06 | [-2.539e-06, 9.333e-06] ∋0 | [-65.49, 17.81] ∋0 | 2.131e-04 | 2/7 | 91 | -0.1311 | False | PAS D'EDGE | **PAS D'EDGE** |
| J | ETHUSDT | 1h | B0 | -6.269e-05 | [-1.428e-04, 1.987e-05] ∋0 | [-62.88, -4.867] excl.0 | 3.279e-06 | 1/7 | 210 | -0.2798 | False | PAS D'EDGE | **PAS D'EDGE** |
| A | ETHUSDT | 4h | B0 | -2.126e-04 | [-5.232e-04, 1.085e-04] ∋0 | [-141.1, 26.16] ∋0 | 1.731e-04 | 1/7 | 76 | -0.2108 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | ETHUSDT | 4h | B1 | 1.451e-05 | [-5.683e-05, 8.472e-05] ∋0 | [-284, 2.722] ∋0 | 2.330e-05 | 1/7 | 21 | -0.1544 | False | NON CONCLUANT | **NON CONCLUANT** |
| H | ETHUSDT | 4h | B2 | 3.780e-06 | [-1.642e-05, 2.163e-05] ∋0 | [-308, -6.822] excl.0 | 3.322e-05 | 1/7 | 17 | -0.09591 | False | NON CONCLUANT | **NON CONCLUANT** |
| J | ETHUSDT | 4h | B0 | -1.507e-04 | [-4.652e-04, 1.713e-04] ∋0 | [-100.6, 119.2] ∋0 | 0.0137 | 4/7 | 53 | -0.1988 | False | PAS D'EDGE | **PAS D'EDGE** |
| A | SOLUSDT | 1h | B0 | -1.062e-04 | [-2.277e-04, 1.573e-05] ∋0 | [-41.01, 59.61] ∋0 | 0.02757 | 4/7 | 265 | -0.3151 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | SOLUSDT | 1h | B1 | 1.931e-07 | [-3.180e-05, 3.129e-05] ∋0 | [-41.11, 96.72] ∋0 | 0.06081 | 4/7 | 98 | -0.1853 | False | PAS D'EDGE | **PAS D'EDGE** |
| H | SOLUSDT | 1h | B2 | -3.393e-06 | [-1.507e-05, 6.526e-06] ∋0 | [-52.77, 91.6] ∋0 | 0.03636 | 3/7 | 80 | -0.1395 | False | NON CONCLUANT | **NON CONCLUANT** |
| J | SOLUSDT | 1h | B0 | -1.573e-04 | [-2.831e-04, -3.255e-05] excl.0 | [-107.5, -21.68] excl.0 | 6.044e-07 | 0/7 | 191 | -0.3497 | False | PAS D'EDGE | **PAS D'EDGE** |
| A | SOLUSDT | 4h | B0 | -3.925e-04 | [-8.843e-04, 1.019e-04] ∋0 | [-120.8, 247.2] ∋0 | 0.06259 | 4/7 | 68 | -0.269 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | SOLUSDT | 4h | B1 | 3.919e-06 | [-1.059e-04, 1.117e-04] ∋0 | [-133.5, 512.9] ∋0 | 0.1793 | 2/7 | 26 | -0.1609 | False | NON CONCLUANT | **NON CONCLUANT** |
| H | SOLUSDT | 4h | B2 | -4.555e-05 | [-1.060e-04, 8.873e-06] ∋0 | [-313.6, 488.5] ∋0 | 0.03619 | 0/7 | 17 | -0.1609 | False | NON CONCLUANT | **NON CONCLUANT** |
| J | SOLUSDT | 4h | B0 | -4.435e-04 | [-9.255e-04, 5.337e-05] ∋0 | [-173.9, 189.1] ∋0 | 0.01367 | 3/7 | 62 | -0.2388 | False | NON CONCLUANT | **NON CONCLUANT** |

## Notes §9 / lecture IC

- **IC apparié ∋ 0 et N ≥ 40** → `verdict_compare` rend **PAS D'EDGE** (et non NON CONCLUANT). Lecture de §9 : l’IC qui contient 0 bloque EDGE, mais avec N suffisant le verdict n’est pas « non concluant ». **Sans impact** sur le total **0 EDGE / 48**.
- **INFO B6 ATR** : le lab B6 laisse passer un ATR **UNKNOWN** ; le live le met en **PENDING**. Pas d’impact sur ce run — ne concerne que les barres **avant WF1**.

## Synthèse verdict_final (base / adverse)

Format : `verdict_final base / verdict_final adverse`.

| Symbole×TF | A | B | H | J |
|---|---|---|---|---|
| BTCUSDT 1h | PAS D'EDGE / PAS D'EDGE | PAS D'EDGE / PAS D'EDGE | **NON CONCLUANT / PAS D'EDGE** | PAS D'EDGE / PAS D'EDGE |
| BTCUSDT 4h | NON CONCLUANT / NON CONCLUANT | NON CONCLUANT / NON CONCLUANT | NON CONCLUANT / NON CONCLUANT | **NON CONCLUANT / PAS D'EDGE** |
| ETHUSDT 1h | PAS D'EDGE / PAS D'EDGE | PAS D'EDGE / PAS D'EDGE | PAS D'EDGE / PAS D'EDGE | PAS D'EDGE / PAS D'EDGE |
| ETHUSDT 4h | PAS D'EDGE / PAS D'EDGE | NON CONCLUANT / NON CONCLUANT | NON CONCLUANT / NON CONCLUANT | PAS D'EDGE / PAS D'EDGE |
| SOLUSDT 1h | PAS D'EDGE / PAS D'EDGE | PAS D'EDGE / PAS D'EDGE | **PAS D'EDGE / NON CONCLUANT** | PAS D'EDGE / PAS D'EDGE |
| SOLUSDT 4h | PAS D'EDGE / PAS D'EDGE | NON CONCLUANT / NON CONCLUANT | NON CONCLUANT / NON CONCLUANT | NON CONCLUANT / NON CONCLUANT |

**Cases qui diffèrent base ↔ adverse (3) :**

| Case | base | adverse |
|---|---|---|
| BTCUSDT 1h · H | NON CONCLUANT | PAS D'EDGE |
| BTCUSDT 4h · J | NON CONCLUANT | PAS D'EDGE |
| SOLUSDT 1h · H | PAS D'EDGE | NON CONCLUANT |

## Séries VP1 (sha256)

| Symbole | TF | sha256 |
|---|---|---|
| BTCUSDT | 1h | `3fe8b4708b6953c0331b23d0facb2b9b773574ab9bc66a197e9c639d28da0d88` |
| BTCUSDT | 4h | `cd8bef9a07f70904dcfc414224411e2ceaeb37b05205c743e1fe87c0bae40782` |
| BTCUSDT | 1d | `1d04e6bbee290adedc5778823302a4cf4b4de36af7bab3fdd9ede1a7da8ef819` |
| ETHUSDT | 1h | `a1e6ee7841ff48538a256455bfe6e07a1a8d844da9ea51c77c319e1082d77083` |
| ETHUSDT | 4h | `67f46cf63f0b3bf2d5d640e0967ad613130349a0d7dd04d588889f8761fda756` |
| ETHUSDT | 1d | `527f6d464dec9ea30ced0b515249dcb128ae62e3e4f5e2072342f23bf9759623` |
| SOLUSDT | 1h | `7a798cb75dea3f33c2a1a259f9ec1c2d0dc3a3d4989a82cc2e5d6be07b9539f7` |
| SOLUSDT | 4h | `0c75aed211b7cfcd851bc2f00d09dc803e1001779683f79a5c0119eea4e623df` |
| SOLUSDT | 1d | `84c36bf4756517d57bf381757753fa1a111f6f7459399cf64bb0ae368a8c7096` |

## Rejouer

```bash
cd ichivol-app/engine
python -m vp3.j1_run /tmp/vp3_j1_results.jsonl 10000
```

