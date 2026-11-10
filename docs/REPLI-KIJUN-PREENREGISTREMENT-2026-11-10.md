# Entrée sur repli (Kijun) : pré-enregistrement (2026-11-10)

**Statut : accepté par le propriétaire le 2026-11-10 (pause VP levée pour ce seul test). Aucun résultat regardé à la date de l'amendement.**

## Pourquoi
552 signaux BUY/SELL 1h du pipeline actuel (21/09 → 10/11/2026, `signal_evidence`) : 20 % à l'objectif, 66 % au stop,
−0,20 R par trade avant frais. Les entrées sur fort volume relatif sont les pires (RVOL > 2,5 : −0,42 R) : on entre
quand le mouvement est fait. Hypothèse : dans la même tendance Ichimoku, entrer sur le retour du prix à la Kijun.

## Règle (figée, aucun paramètre à régler)
Fichier : [`repli-artifacts/rulesets.json`](repli-artifacts/rulesets.json), lu par `app/strategy_lab/ruleset.py`.

| | LONG (`REPLI-KIJUN-LONG-1h`) |
|---|---|
| Tendance | `price_above_kumo` et `tenkan_above_kijun` |
| Déclencheur | `kijun_bounce` (rebond sur la Kijun dans le sens du trade) |
| Filtre | `rvol_max` 2,5 |
| Entrée | ouverture de la bougie suivante |
| Stop / objectif | 1,5 ATR / 3 ATR (2 R, comme le compte paper) |

Le pendant SHORT (`REPLI-KIJUN-SHORT-1h`) est écrit mais **hors test historique** : la crypto au comptant ne se vend
pas à découvert et les CFD n'ont que quelques mois d'historique. Il ne pourra être jugé qu'en trades fantômes.

## Données, plis, coûts
Ceux de `docs/VALIDATION-PROTOCOL.md`, sans changement : BTCUSDT, ETHUSDT, SOLUSDT en 1h ; développement jusqu'au
2024-12-31, plis WF1 à WF7 ; coûts base et adverse. **Ni la validation 2025 ni le holdout 2026 ne sont ouverts.**

## Hypothèses et compteur T10b
| # | hypothesis_id | symbole | TF | coûts |
|---|---|---|---|---|
| 49 | `BR-BTCUSDT-1h-base` | BTCUSDT | 1h | base |
| 50 | `BR-ETHUSDT-1h-base` | ETHUSDT | 1h | base |
| 51 | `BR-SOLUSDT-1h-base` | SOLUSDT | 1h | base |

N passe de 48 à **51** (à reporter dans `VP-T10B-LEDGER.md` au commit). Le DSR se calcule avec N = 51.

## Verdict
Critères du §9 de VP0, inchangés : EDGE, PAS D'EDGE ou NON CONCLUANT, par hypothèse, sur l'agrégat des plis de test.
Comparaison appariée avec B7 (entrée actuelle) et B0 (buy & hold). Un seul run. Si PAS D'EDGE : la règle est
abandonnée, pas de variante de paramètres.

## Amendement du 2026-11-10, avant tout run
Précisions apportées en branchant la règle dans le harnais `vp3/`, sans avoir vu aucun résultat :
- **Exécution** : celle du harnais commun VP2 (§6), comme B1 à B8. Stop 1,5 ATR et objectif 2 R comme annoncé, plus
  le **time-stop de 48 barres**, une seule position, tout le capital. Le compte paper n'a pas de time-stop.
- **Verdict d'une hypothèse** : critères §9 (1) à (6) sur BR seule (espérance > 0, IC des trades hors 0, DSR ≥ 0,95,
  ≥ 5 plis positifs sur 7, ≥ 40 trades, maxDD < 35 % par pli). EDGE en base non confirmé en adverse = NON CONCLUANT.
- **Comparaisons appariées** BR contre B7 et BR contre B0 : rapportées à côté, hors verdict.
- **DSR** : N = 51 ; σ = écart-type des Sharpe annualisés des 9 séries du run (BR, B7, B0 × 3 symboles), méthode NT1/J1.
- **Données** : séries VP1 retéléchargées sur cette machine ; le run n'a lieu que si leurs sha256 sont ceux de
  `VP3-REPORT-FINAL.md`.

Code : `vp3/repli.py`, `vp3/repli_run.py`, tests `tests/vp3/test_repli.py`.

## Reste à faire avant le run
1. Commit de l'amendement et du code.
2. Vérification des sha256, run (`python -m vp3.repli_run docs/repli-artifacts/br_results.json 10000`).
3. Rapport `docs/REPLI-KIJUN-REPORT.md`.
