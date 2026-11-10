# Entrée sur repli (Kijun) : pré-enregistrement (2026-11-10)

**Statut : proposé. Aucun run lancé, aucun résultat regardé.** À committer avant tout run (règle VP0).
Le programme VP est en pause sur décision du propriétaire : ce test demande son accord explicite.

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

## Reste à faire avant le run
1. Accord du propriétaire, commit de ce fichier et du ledger.
2. Brancher la règle dans le harnais `vp3/` (nouvelle entrée `BR` à côté de B7) avec ses tests.
3. Run, rapport `docs/REPLI-KIJUN-REPORT.md`.
