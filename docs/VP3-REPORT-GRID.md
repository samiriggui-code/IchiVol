# VP3 — grille A / B / H — **v2** (VP-NT1)

**Job :** VP-NT1 étape 2 · branche `cursor/vp-nt1-a2fe`  
**Protocole :** `VP0-2026-09-26` · **N T10b gelé = 24**  
**Coûts :** base + adverse · **n_boot :** 10 000  
**DSR :** σ(SR_ann) sur 24 hyps → SR*_ann → PSR à l’échelle **barre** (`dsr_bar_scaled`)  
**Time-stop :** VP2-R1 · **Date run :** 2026-09-27

> **Hors scope :** Q J (B7), B3/B4/B6, retuning. Artefact JSON : [`docs/vp3-artifacts/nt1_results.json`](./vp3-artifacts/nt1_results.json).

### Conclusion

**0 EDGE / 36** cases (18 base + 18 adverse). SR*_ann = **0.897** (base) / **1.249** (adverse). Meilleur DSR_i = **0.49** (B2 · SOLUSDT 4h · 26 trades). B1/B2/B5 = **PAS D'EDGE** ou **NON CONCLUANT** partout (4h : N trades souvent &lt; 40). **Aucune case n’est éligible** à la validation 2025.

### Contamination pré-gel (rappel)

Lab `research_lab/runs/2026-09-20` a déjà joué **BTCUSDT / ETHUSDT / SOLUSDT** (A=20, B=40). Fenêtres DEV (2025-06-01→2026-01-01) et VAL (2026-01-01→2026-09) marquent validation **2025 S2** et **holdout 2026** comme **« déjà vus »** pour ces symboles. N T10b **inchangé** (autre harnais). La règle HTF B5 VP a été formalisée **après** le Lab (`#148`, 2026-09-26).

## σ / SR* (N=24)

| Profil | σ(SR_ann) | SR*_ann | SR*_bar 1h | SR*_bar 4h |
|---|---:|---:|---:|---:|
| base | 0.645419 | 0.897347 | 0.00958756 | 0.0191751 |
| adverse | 0.898019 | 1.24854 | 0.0133399 | 0.0266798 |

## 24 SR_ann (base + adverse)

| B* | symbole | TF | SR_ann base | DSR base | SR_ann adverse | DSR adverse | N trades base |
|---|---|---|---:|---:|---:|---:|---:|
| B0 | BTCUSDT | 1h | 0.77664 | 0.4106 | 0.77229 | 0.1864 | 7 |
| B0 | BTCUSDT | 4h | 0.81976 | 0.4423 | 0.81534 | 0.2087 | 7 |
| B0 | ETHUSDT | 1h | 0.49602 | 0.2263 | 0.49255 | 0.07857 | 7 |
| B0 | ETHUSDT | 4h | 0.50928 | 0.2339 | 0.50576 | 0.08233 | 7 |
| B0 | SOLUSDT | 1h | 0.927 | 0.5222 | 0.92481 | 0.2719 | 7 |
| B0 | SOLUSDT | 4h | 0.94242 | 0.5337 | 0.94016 | 0.2812 | 7 |
| B1 | BTCUSDT | 1h | -1.0664 | 1.268e-04 | -2.2588 | 2.954e-11 | 317 |
| B1 | BTCUSDT | 4h | 0.2783 | 0.1208 | -0.065943 | 0.007043 | 71 |
| B1 | ETHUSDT | 1h | -1.0754 | 1.130e-04 | -2.0792 | 2.069e-10 | 296 |
| B1 | ETHUSDT | 4h | -0.37353 | 0.008845 | -0.64781 | 2.014e-04 | 76 |
| B1 | SOLUSDT | 1h | 0.81619 | 0.4391 | 0.24768 | 0.03021 | 265 |
| B1 | SOLUSDT | 4h | 0.60565 | 0.2917 | 0.45249 | 0.06766 | 68 |
| B2 | BTCUSDT | 1h | -0.11887 | 0.02867 | -0.87732 | 3.550e-05 | 129 |
| B2 | BTCUSDT | 4h | 0.54326 | 0.2474 | 0.33249 | 0.04082 | 22 |
| B2 | ETHUSDT | 1h | -0.10664 | 0.03011 | -0.7945 | 6.255e-05 | 119 |
| B2 | ETHUSDT | 4h | -0.74088 | 9.902e-04 | -0.87367 | 2.770e-05 | 21 |
| B2 | SOLUSDT | 1h | 0.82115 | 0.4425 | 0.44827 | 0.06579 | 98 |
| B2 | SOLUSDT | 4h | 0.88448 | 0.4902 | 0.78837 | 0.1901 | 26 |
| B5 | BTCUSDT | 1h | 0.1854 | 0.09093 | -0.50393 | 5.203e-04 | 99 |
| B5 | BTCUSDT | 4h | 0.83615 | 0.452 | 0.6618 | 0.1282 | 14 |
| B5 | ETHUSDT | 1h | -0.02123 | 0.04274 | -0.60547 | 2.476e-04 | 91 |
| B5 | ETHUSDT | 4h | -0.71002 | 0.001151 | -0.8203 | 3.940e-05 | 17 |
| B5 | SOLUSDT | 1h | 0.65827 | 0.3247 | 0.31751 | 0.03968 | 80 |
| B5 | SOLUSDT | 4h | 0.39511 | 0.1714 | 0.31563 | 0.03949 | 17 |

## Compares — profil **base**

| Q | Symbole | TF | Δmean | IC Δ | IC trades Bi | DSR_i | +plis | N | maxDD | beats | verdict | verdict_final |
|---|---|---|---:|---|---|---:|---:|---:|---:|---|---|---|
| A | BTCUSDT | 1h | -7.037e-05 | [-1.321e-04, -6.120e-06] excl.0 | [-38.7, -1.61] excl.0 | 1.268e-04 | 2/7 | 317 | -0.268 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | BTCUSDT | 1h | 1.993e-05 | [4.274e-06, 3.548e-05] excl.0 | [-33, 25.8] ∋0 | 0.02867 | 3/7 | 129 | -0.132 | False | PAS D'EDGE | **PAS D'EDGE** |
| H | BTCUSDT | 1h | 3.614e-06 | [-2.230e-06, 9.737e-06] ∋0 | [-27.1, 39.8] ∋0 | 0.09093 | 3/7 | 99 | -0.12 | False | NON CONCLUANT | **NON CONCLUANT** |
| A | BTCUSDT | 4h | -1.853e-04 | [-4.333e-04, 6.881e-05] ∋0 | [-53.5, 106] ∋0 | 0.1208 | 3/7 | 71 | -0.223 | False | NON CONCLUANT | **NON CONCLUANT** |
| B | BTCUSDT | 4h | -8.131e-08 | [-6.068e-05, 5.754e-05] ∋0 | [-58.8, 191] ∋0 | 0.2474 | 0/7 | 22 | -0.127 | False | NON CONCLUANT | **NON CONCLUANT** |
| H | BTCUSDT | 4h | 3.213e-06 | [-1.979e-05, 2.496e-05] ∋0 | [-35.6, 264] ∋0 | 0.452 | 0/7 | 14 | -0.0343 | False | NON CONCLUANT | **NON CONCLUANT** |
| A | ETHUSDT | 1h | -6.302e-05 | [-1.410e-04, 1.753e-05] ∋0 | [-46.7, -0.661] excl.0 | 1.130e-04 | 1/7 | 296 | -0.258 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | ETHUSDT | 1h | 2.250e-05 | [4.316e-06, 4.088e-05] excl.0 | [-39.7, 33.4] ∋0 | 0.03011 | 3/7 | 119 | -0.127 | False | PAS D'EDGE | **PAS D'EDGE** |
| H | ETHUSDT | 1h | 1.160e-06 | [-4.673e-06, 6.964e-06] ∋0 | [-42.5, 41.9] ∋0 | 0.04274 | 2/7 | 91 | -0.113 | False | PAS D'EDGE | **PAS D'EDGE** |
| A | ETHUSDT | 4h | -1.900e-04 | [-4.998e-04, 1.311e-04] ∋0 | [-120, 50] ∋0 | 0.008845 | 2/7 | 76 | -0.192 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | ETHUSDT | 4h | -2.634e-06 | [-7.374e-05, 6.700e-05] ∋0 | [-262, 26.8] ∋0 | 9.902e-04 | 1/7 | 21 | -0.147 | False | NON CONCLUANT | **NON CONCLUANT** |
| H | ETHUSDT | 4h | 2.532e-06 | [-1.798e-05, 2.005e-05] ∋0 | [-285, 17.1] ∋0 | 0.001151 | 1/7 | 17 | -0.0916 | False | NON CONCLUANT | **NON CONCLUANT** |
| A | SOLUSDT | 1h | -8.583e-05 | [-2.067e-04, 3.545e-05] ∋0 | [-17.6, 87.7] ∋0 | 0.4391 | 4/7 | 265 | -0.273 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | SOLUSDT | 1h | -1.280e-05 | [-4.459e-05, 1.822e-05] ∋0 | [-17.1, 123] ∋0 | 0.4425 | 4/7 | 98 | -0.164 | False | PAS D'EDGE | **PAS D'EDGE** |
| H | SOLUSDT | 1h | -4.796e-06 | [-1.668e-05, 5.108e-06] ∋0 | [-28.4, 118] ∋0 | 0.3247 | 5/7 | 80 | -0.129 | False | PAS D'EDGE | **PAS D'EDGE** |
| A | SOLUSDT | 4h | -3.723e-04 | [-8.615e-04, 1.208e-04] ∋0 | [-97.5, 276] ∋0 | 0.2917 | 4/7 | 68 | -0.259 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | SOLUSDT | 4h | -9.180e-06 | [-1.191e-04, 9.847e-05] ∋0 | [-109, 540] ∋0 | 0.4902 | 2/7 | 26 | -0.159 | False | NON CONCLUANT | **NON CONCLUANT** |
| H | SOLUSDT | 4h | -4.838e-05 | [-1.097e-04, 6.409e-06] ∋0 | [-291, 514] ∋0 | 0.1714 | 0/7 | 17 | -0.159 | False | NON CONCLUANT | **NON CONCLUANT** |

## Compares — profil **adverse**

| Q | Symbole | TF | Δmean | IC Δ | IC trades Bi | DSR_i | +plis | N | maxDD | beats | verdict | verdict_final |
|---|---|---|---:|---|---|---:|---:|---:|---:|---|---|---|
| A | BTCUSDT | 1h | -9.482e-05 | [-1.570e-04, -3.002e-05] excl.0 | [-58.6, -23.2] excl.0 | 2.954e-11 | 0/7 | 317 | -0.324 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | BTCUSDT | 1h | 3.459e-05 | [1.849e-05, 5.064e-05] excl.0 | [-55.6, 1.92] ∋0 | 3.550e-05 | 2/7 | 129 | -0.168 | False | PAS D'EDGE | **PAS D'EDGE** |
| H | BTCUSDT | 1h | 5.953e-06 | [-4.910e-08, 1.231e-05] ∋0 | [-50.4, 15.6] ∋0 | 5.203e-04 | 3/7 | 99 | -0.157 | False | PAS D'EDGE | **PAS D'EDGE** |
| A | BTCUSDT | 4h | -2.063e-04 | [-4.548e-04, 4.869e-05] ∋0 | [-76.3, 81.5] ∋0 | 0.007043 | 3/7 | 71 | -0.243 | False | NON CONCLUANT | **NON CONCLUANT** |
| B | BTCUSDT | 4h | 1.521e-05 | [-4.571e-05, 7.349e-05] ∋0 | [-82.1, 166] ∋0 | 0.04082 | 0/7 | 22 | -0.138 | False | NON CONCLUANT | **NON CONCLUANT** |
| H | BTCUSDT | 4h | 5.706e-06 | [-1.707e-05, 2.787e-05] ∋0 | [-59.5, 239] ∋0 | 0.1282 | 0/7 | 14 | -0.0345 | False | NON CONCLUANT | **NON CONCLUANT** |
| A | ETHUSDT | 1h | -8.578e-05 | [-1.642e-04, -4.463e-06] excl.0 | [-66.2, -22] excl.0 | 2.069e-10 | 1/7 | 296 | -0.315 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | ETHUSDT | 1h | 3.624e-05 | [1.776e-05, 5.516e-05] excl.0 | [-62.5, 9.4] ∋0 | 6.255e-05 | 2/7 | 119 | -0.147 | False | PAS D'EDGE | **PAS D'EDGE** |
| H | ETHUSDT | 1h | 3.341e-06 | [-2.539e-06, 9.333e-06] ∋0 | [-65.5, 17.8] ∋0 | 2.476e-04 | 2/7 | 91 | -0.131 | False | PAS D'EDGE | **PAS D'EDGE** |
| A | ETHUSDT | 4h | -2.126e-04 | [-5.232e-04, 1.085e-04] ∋0 | [-141, 26.2] ∋0 | 2.014e-04 | 1/7 | 76 | -0.211 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | ETHUSDT | 4h | 1.451e-05 | [-5.683e-05, 8.472e-05] ∋0 | [-284, 2.72] ∋0 | 2.770e-05 | 1/7 | 21 | -0.154 | False | NON CONCLUANT | **NON CONCLUANT** |
| H | ETHUSDT | 4h | 3.780e-06 | [-1.642e-05, 2.163e-05] ∋0 | [-308, -6.82] excl.0 | 3.940e-05 | 1/7 | 17 | -0.0959 | False | NON CONCLUANT | **NON CONCLUANT** |
| A | SOLUSDT | 1h | -1.062e-04 | [-2.277e-04, 1.573e-05] ∋0 | [-41, 59.6] ∋0 | 0.03021 | 4/7 | 265 | -0.315 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | SOLUSDT | 1h | 1.931e-07 | [-3.180e-05, 3.129e-05] ∋0 | [-41.1, 96.7] ∋0 | 0.06579 | 4/7 | 98 | -0.185 | False | PAS D'EDGE | **PAS D'EDGE** |
| H | SOLUSDT | 1h | -3.393e-06 | [-1.507e-05, 6.526e-06] ∋0 | [-52.8, 91.6] ∋0 | 0.03968 | 3/7 | 80 | -0.14 | False | NON CONCLUANT | **NON CONCLUANT** |
| A | SOLUSDT | 4h | -3.925e-04 | [-8.843e-04, 1.019e-04] ∋0 | [-121, 247] ∋0 | 0.06766 | 4/7 | 68 | -0.269 | False | PAS D'EDGE | **PAS D'EDGE** |
| B | SOLUSDT | 4h | 3.919e-06 | [-1.059e-04, 1.117e-04] ∋0 | [-134, 513] ∋0 | 0.1901 | 2/7 | 26 | -0.161 | False | NON CONCLUANT | **NON CONCLUANT** |
| H | SOLUSDT | 4h | -4.555e-05 | [-1.060e-04, 8.873e-06] ∋0 | [-314, 489] ∋0 | 0.03949 | 0/7 | 17 | -0.161 | False | NON CONCLUANT | **NON CONCLUANT** |

## Synthèse verdict_final (base / adverse)

Format : `verdict_final base / verdict_final adverse`.

| Symbole×TF | A | B | H |
|---|---|---|---|
| BTCUSDT 1h | PAS D'EDGE / PAS D'EDGE | PAS D'EDGE / PAS D'EDGE | **NON CONCLUANT / PAS D'EDGE** |
| BTCUSDT 4h | NON CONCLUANT / NON CONCLUANT | NON CONCLUANT / NON CONCLUANT | NON CONCLUANT / NON CONCLUANT |
| ETHUSDT 1h | PAS D'EDGE / PAS D'EDGE | PAS D'EDGE / PAS D'EDGE | PAS D'EDGE / PAS D'EDGE |
| ETHUSDT 4h | PAS D'EDGE / PAS D'EDGE | NON CONCLUANT / NON CONCLUANT | NON CONCLUANT / NON CONCLUANT |
| SOLUSDT 1h | PAS D'EDGE / PAS D'EDGE | PAS D'EDGE / PAS D'EDGE | **PAS D'EDGE / NON CONCLUANT** |
| SOLUSDT 4h | PAS D'EDGE / PAS D'EDGE | NON CONCLUANT / NON CONCLUANT | NON CONCLUANT / NON CONCLUANT |

**Cases qui diffèrent base ↔ adverse (2) :**

| Case | base | adverse |
|---|---|---|
| BTCUSDT 1h · H | NON CONCLUANT | PAS D'EDGE |
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
python -m vp3.nt1_run /tmp/vp3_nt1_results.jsonl 10000
```

---

## Historique — v1 (VP-GRID1, N trials = 1 provisoire)

<details>
<summary>Rapport GRID1 v1 (N=1, base seul, sans adverse)</summary>

# VP3 — grille A / B / H (VP-GRID1)

**Job :** VP-GRID1 · branche `cursor/vp-grid1-a2fe`  
**Protocole :** `VP0-2026-09-26` + clarification VP2-R1 (§12, 2026-09-26)  
**Coûts :** base · **n_boot :** 10 000 · **DSR N trials :** 1 (non figé)  
**Time-stop :** entrée = barre 1 → sortie `entry+(n−1)·bar`  
**Date run :** 2026-09-27

> Pas de claim **EDGE**. **Hors scope :** Q J (B7), figer N T10b, profil adverse.

## Séries VP1 (sha256 + complétude)

| Symbole | TF | n_bars | expected | missing | gap_frac | sha256 |
|---|---|---:|---:|---:|---:|---|
| BTCUSDT | 1h | 52565 | 52584 | 19 | 0.0361% | `3fe8b4708b69…` |
| BTCUSDT | 4h | 13146 | 13146 | 0 | 0.0000% | `cd8bef9a07f7…` |
| BTCUSDT | 1d | 2191 | 2191 | 0 | 0.0000% | `1d04e6bbee29…` |
| ETHUSDT | 1h | 52565 | 52584 | 19 | 0.0361% | `a1e6ee7841ff…` |
| ETHUSDT | 4h | 13146 | 13146 | 0 | 0.0000% | `67f46cf63f0b…` |
| ETHUSDT | 1d | 2191 | 2191 | 0 | 0.0000% | `527f6d464dec…` |
| SOLUSDT | 1h | 52565 | 52584 | 19 | 0.0361% | `7a798cb75dea…` |
| SOLUSDT | 4h | 13146 | 13146 | 0 | 0.0000% | `0c75aed211b7…` |
| SOLUSDT | 1d | 2191 | 2191 | 0 | 0.0000% | `84c36bf47565…` |

Full digests :

```
BTCUSDT 1h 3fe8b4708b6953c0331b23d0facb2b9b773574ab9bc66a197e9c639d28da0d88
BTCUSDT 4h cd8bef9a07f70904dcfc414224411e2ceaeb37b05205c743e1fe87c0bae40782
BTCUSDT 1d 1d04e6bbee290adedc5778823302a4cf4b4de36af7bab3fdd9ede1a7da8ef819
ETHUSDT 1h a1e6ee7841ff48538a256455bfe6e07a1a8d844da9ea51c77c319e1082d77083
ETHUSDT 4h 67f46cf63f0b3bf2d5d640e0967ad613130349a0d7dd04d588889f8761fda756
ETHUSDT 1d 527f6d464dec9ea30ced0b515249dcb128ae62e3e4f5e2072342f23bf9759623
SOLUSDT 1h 7a798cb75dea3f33c2a1a259f9ec1c2d0dc3a3d4989a82cc2e5d6be07b9539f7
SOLUSDT 4h 0c75aed211b7cfcd851bc2f00d09dc803e1001779683f79a5c0119eea4e623df
SOLUSDT 1d 84c36bf4756517d57bf381757753fa1a111f6f7459399cf64bb0ae368a8c7096
```

### Note — 19 barres 1h manquantes (Vision)

Les **mêmes 10 plages** (19 barres) manquent sur **BTCUSDT, ETHUSDT et SOLUSDT** 1h (timestamps identiques) :

| from (UTC) | to (UTC) | missing |
|---|---|---:|
| 2020-11-30 06:00 | 2020-11-30 07:00 | 1 |
| 2020-12-21 15:00 | 2020-12-21 18:00 | 3 |
| 2020-12-25 02:00 | 2020-12-25 03:00 | 1 |
| 2021-02-11 04:00 | 2021-02-11 05:00 | 1 |
| 2021-03-06 02:00 | 2021-03-06 03:00 | 1 |
| 2021-04-20 02:00 | 2021-04-20 04:00 | 2 |
| 2021-04-25 05:00 | 2021-04-25 08:00 | 3 |
| 2021-08-13 02:00 | 2021-08-13 06:00 | 4 |
| 2021-09-29 07:00 | 2021-09-29 09:00 | 2 |
| 2023-03-24 13:00 | 2023-03-24 14:00 | 1 |

**Time-stop vs trous :** le décompte S1 est en **temps réel** `(t − entry_time) // bar_seconds` (VP2-R1). Un trade qui traverse un trou atteint donc le seuil time-stop avec **moins de 48 barres réellement présentes** dans la série. Documenté seulement — **pas de changement de règle** dans cette PR.

---

## BTCUSDT · 1h

*(v3 — remplace la v2 post-VP-FIX1 ; time-stop VP2-R1)*

| Q | Pair | bi_beats | N_i | exp_i | DSR_i | pos_i | N_j | exp_j / Sharpe_j | DSR_j | Δmean IC excl.0 | Δmean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | B1 vs B0 | **false** | 317 | -20.48 | 0.02347 | 2/7 | 7 | Sharpe=0.7766 | 0.927 | True | -7.04e-05 |
| B | B2 vs B1 | **false** | 129 | -4.167 | 0.412 | 3/7 | 317 | -20.48 | 0.02347 | True | 1.99e-05 |
| H | B5 vs B2 | **false** | 99 | 5.799 | 0.636 | 3/7 | 129 | -4.167 | 0.412 | False | 3.61e-06 |

## BTCUSDT · 4h

| Q | Pair | bi_beats | N_i | exp_i | DSR_i | pos_i | N_j | exp_j / Sharpe_j | DSR_j | Δmean IC excl.0 | Δmean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | B1 vs B0 | **false** | 71 | 24.21 | 0.7007 | 3/7 | 7 | Sharpe=0.8198 | 0.9375 | False | -1.85e-04 |
| B | B2 vs B1 | **false** | 22 | 63.9 | 0.8525 | 0/7 | 71 | 24.21 | 0.7007 | False | -8.13e-08 |
| H | B5 vs B2 | **false** | 14 | 114.4 | 0.9503 | 0/7 | 22 | 63.9 | 0.8525 | False | 3.21e-06 |

## ETHUSDT · 1h

| Q | Pair | bi_beats | N_i | exp_i | DSR_i | pos_i | N_j | exp_j / Sharpe_j | DSR_j | Δmean IC excl.0 | Δmean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | B1 vs B0 | **false** | 296 | -24.14 | 0.0222 | 1/7 | 7 | Sharpe=0.496 | 0.8234 | False | -6.30e-05 |
| B | B2 vs B1 | **false** | 119 | -3.679 | 0.4209 | 3/7 | 296 | -24.14 | 0.0222 | True | 2.25e-05 |
| H | B5 vs B2 | **false** | 91 | -1.514 | 0.4841 | 2/7 | 119 | -3.679 | 0.4209 | False | 1.16e-06 |

## ETHUSDT · 4h

| Q | Pair | bi_beats | N_i | exp_i | DSR_i | pos_i | N_j | exp_j / Sharpe_j | DSR_j | Δmean IC excl.0 | Δmean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | B1 vs B0 | **false** | 76 | -37.04 | 0.2428 | 2/7 | 7 | Sharpe=0.5093 | 0.8296 | False | -1.90e-04 |
| B | B2 vs B1 | **false** | 21 | -128.7 | 0.08093 | 1/7 | 76 | -37.04 | 0.2428 | False | -2.63e-06 |
| H | B5 vs B2 | **false** | 17 | -149.8 | 0.08906 | 1/7 | 21 | -128.7 | 0.08093 | False | 2.53e-06 |

## SOLUSDT · 1h

| Q | Pair | bi_beats | N_i | exp_i | DSR_i | pos_i | N_j | exp_j / Sharpe_j | DSR_j | Δmean IC excl.0 | Δmean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | B1 vs B0 | **false** | 265 | 34.96 | 0.9382 | 4/7 | 7 | Sharpe=0.927 | 0.9589 | False | -8.58e-05 |
| B | B2 vs B1 | **false** | 98 | 51.94 | 0.9405 | 4/7 | 265 | 34.96 | 0.9382 | False | -1.28e-05 |
| H | B5 vs B2 | **false** | 80 | 44.99 | 0.8946 | 5/7 | 98 | 51.94 | 0.9405 | False | -4.80e-06 |

## SOLUSDT · 4h

| Q | Pair | bi_beats | N_i | exp_i | DSR_i | pos_i | N_j | exp_j / Sharpe_j | DSR_j | Δmean IC excl.0 | Δmean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | B1 vs B0 | **false** | 68 | 88.13 | 0.8725 | 4/7 | 7 | Sharpe=0.9424 | 0.9616 | False | -3.72e-04 |
| B | B2 vs B1 | **false** | 26 | 221.3 | 0.955 | 2/7 | 68 | 88.13 | 0.8725 | False | -9.18e-06 |
| H | B5 vs B2 | **false** | 17 | 115.2 | 0.7723 | 0/7 | 26 | 221.3 | 0.955 | False | -4.84e-05 |

## Synthèse

| Symbole×TF | A (B1≻B0) | B (B2≻B1) | H (B5≻B2) |
|---|---|---|---|
| BTCUSDT 1h | false (Δ<0) | false (Δ>0 DSR=0.41) | false (IC∋0) |
| BTCUSDT 4h | false (IC∋0) | false (IC∋0) | false (IC∋0) |
| ETHUSDT 1h | false (IC∋0) | false (Δ>0 DSR=0.42) | false (IC∋0) |
| ETHUSDT 4h | false (IC∋0) | false (IC∋0) | false (IC∋0) |
| SOLUSDT 1h | false (IC∋0) | false (IC∋0) | false (IC∋0) |
| SOLUSDT 4h | false (IC∋0) | false (IC∋0) | false (IC∋0) |

### Lecture courte

- Aucun `bi_beats_bj=true` sur la grille (confirmé).
- B0 reste difficile à battre en equity sur plusieurs couples.
- **Cas DSR_i ≥ 0.95** (liste exhaustive sur la grille) :
  - BTCUSDT 4h · H (B5) · DSR_i = **0.9503**
  - SOLUSDT 4h · B (B2) · DSR_i = **0.955**
- DSR calculés avec **N trials = 1** → **surévalués** ; **non interprétables** avant gel N T10b.
- **4h :** N trades **14–26** → **puissance faible**, aucune conclusion.
- Claim EDGE toujours bloqué (N T10b non figé, adverse non joué, Q J hors scope).

## Rejouer

```bash
cd ichivol-app/engine
python -m vp3.grid_run /tmp/vp3_grid_results.jsonl 10000
```



</details>
