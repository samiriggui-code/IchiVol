# RS-D1 — Rapport : cassure Donchian 4h + sortie de tendance

**Hypothèse :** `RS-D1-U3-4h` · amendement `VP0-2026-09-28b` · spec [`RS-03-DONCHIAN-4H-SPEC.md`](./RS-03-DONCHIAN-4H-SPEC.md) (note d'implémentation §10 bis).
**Run unique :** 2026-09-28 · code figé au commit `1a4eba5` **avant** le run · seed 7 · données de développement seulement (≤ 2024-12-31).
**Données :** VP1 spot 4h, sha256 du manifeste BTC `cd8bef9a…`, ETH `67f46cf6…`, SOL `0c75aed2…` (identiques au rapport VP3). 9 498 barres par actif après troncature, dernière barre 2024-12-31 20:00 UTC.
**Artefacts :** [`rs-artifacts/rsd1_results.json`](./rs-artifacts/rsd1_results.json), journal des trades [`rs-artifacts/rsd1_trades.json`](./rs-artifacts/rsd1_trades.json). Commande : `python -m rs.run` depuis `ichivol-app/engine`.

## Verdict

**CANDIDAT À VALIDATION SUPPLÉMENTAIRE** : les critères D1 à D7 sont tous vrais.

Ce n'est **pas** une stratégie validée. Aucune donnée 2025 ni 2026 n'a été ouverte. La suite (ouvrir la validation 2025, ou non) est **une décision de Samir**.

| # | Critère | Mesure | Résultat |
|---|---------|--------|----------|
| D1 | Rendement net > 0 et borne basse de la moyenne mensuelle > 0 | **+32,9 %** ; moyenne mensuelle +0,70 % [**+0,05 %** ; +1,45 %] | ✅ (borne basse très proche de 0) |
| D2 | maxDD ≤ 15 % | **−5,0 %** | ✅ |
| D3 | Δ mensuel vs B7-P, borne basse > 0 | +1,02 %/mois [**+0,40 %** ; +1,70 %] | ✅ |
| D4 | Calmar > Calmar B0-E | **1,68** contre 0,50 | ✅ |
| D5 | ≥ 2/3 actifs et ≥ 4/7 plis positifs | 3/3 actifs, **6/7** plis (WF3 −2,3 %) | ✅ |
| D6 | > 0 en coûts adverses | **+26,8 %** | ✅ |
| D7 | ≥ 30 trades clôturés | **200** | ✅ |

Intervalles : bootstrap par mois calendaire (42 mois), 10 000 tirages, seed 7, percentile 95 %.

## Comparaison (2021-07-01 → 2024-12-31, capital 5 000, coûts paper)

| | Capital final | Rendement | CAGR | maxDD | Calmar | Exposition moyenne |
|---|---|---|---|---|---|---|
| **RS-D1** | **6 643** | **+32,9 %** | 8,4 % | **−5,0 %** | **1,68** | 5,8 % (max 33 %) |
| RS-D1 coûts adverses | 6 338 | +26,8 % | 7,0 % | −6,1 % | 1,15 | — |
| RS-D1 exécution `open(t+2)` (stress) | 6 823 | +36,5 % | 9,3 % | −4,6 % | 2,02 | — |
| B7-P (paper actuel, R4 #159) | 4 368 | −12,6 % | — | — | — | — |
| B0-E (passif, même exposition 5,8 %) | 5 798 | +16,0 % | 4,3 % | −8,7 % | 0,50 | 5,9 % |
| B0-F (passif 100 % investi) | 15 758 | +215 % | 38,8 % | **−88,8 %** | 0,44 | 100 % |
| Cash | 5 000 | 0 % | — | 0 % | — | 0 % |

## Ce que le résultat dit, et ce qu'il ne dit pas

**Ce que les données excluent (dans ce cadre de développement) :**
- que RS-D1 perde de l'argent en moyenne : la borne basse mensuelle est > 0, même si elle est de justesse ;
- que RS-D1 fasse moins bien que le paper actuel (B7-P) : Δ > 0 avec un intervalle qui exclut 0 ;
- une dépendance aux coûts : les frais pèsent 8,9 % du gain brut, et le résultat reste positif en adverse ;
- une fragilité au délai d'exécution : un décalage d'une barre ne dégrade pas le résultat.

**Ce qu'elles n'excluent pas :**
- **que le timing n'ajoute rien par rapport à une détention passive de même exposition.** Δ mensuel vs B0-E : +0,34 %/mois [−0,10 % ; +0,81 %]. L'intervalle **contient 0**. L'avantage mesuré de RS-D1 sur B0-E porte surtout sur le **risque** (maxDD −5,0 % contre −8,7 %, Calmar 1,68 contre 0,50), pas sur un rendement supérieur établi. Ce n'est pas un critère figé, mais c'est la limite principale du résultat ;
- un effet d'échantillon : 42 mois seulement, 20 mois négatifs sur 42, et la borne basse D1 est à +0,05 %/mois ;
- la dépendance aux grandes tendances : les 3 meilleurs trades font 44 % du P&L et les 5 meilleurs 64 %. Sans les 3 meilleurs, le P&L reste positif (+919 €). C'est attendu pour une stratégie de tendance, et descriptif (non bloquant) ;
- la **multiplicité** : RS-D1 est la 49ᵉ hypothèse du registre T10b. Pas de DSR ici (§11), mais un seul candidat positif sur ~49 essais appelle une validation hors échantillon avant toute conclusion.

**En clair :** avec une exposition moyenne de 6 %, RS-D1 fait **+33 % en 3,5 ans avec une chute maximale de 5 %**. Sur la même période, le paper actuel perd 13 %. C'est un profil **prudent** : il ne remplace pas la détention passive (+215 %, mais −89 % au pire moment), et son rendement absolu reste modeste (8,4 %/an).

## Détail RS-D1 (base, coûts paper)

**Trades :**
- **Volume :** 200 clôturés, 0 ouvert en fin de fenêtre. ETH 71, SOL 70, BTC 59.
- **Réussite :** 38 %, gain moyen +49,3 €, perte moyenne −16,9 €, profit factor 1,78.
- **Espérance :** +8,2 € par trade, **+0,45 R**.
- **Durée :** médiane 88 h (≈ 3,7 jours), moyenne 111 h.
- **Frais :** 159,8 € (commission + friction), soit 8,9 % du brut (1 802,7 €).

**Motifs de sortie :**

| Motif | n | P&L net |
|---|---|---|
| Stop suiveur | 169 | +2 360 € |
| Stop initial | 27 | −729 € |
| Canal (L20) | 3 | −25 € |
| Gap sous le stop | 1 | +37 € |

Le stop suiveur à 3 ATR sort presque toujours avant la sortie de canal : la règle L20 ne joue presque aucun rôle.

**Par actif :** BTC +697 €, ETH +189 €, SOL +756 €.

**Par pli :**

| WF1 | WF2 | WF3 | WF4 | WF5 | WF6 | WF7 |
|---|---|---|---|---|---|---|
| +7,4 % | +1,5 % | −2,3 % | +5,6 % | +7,8 % | +3,7 % | +5,6 % |

**Par année :** 2021 (S2) +7,4 % · 2022 **−0,8 %** · 2023 +13,9 % · 2024 +9,5 %.

En 2022, marché baissier où B0-F perd 83 %, RS-D1 perd 0,8 %.

**Risque :**
- **maxDD :** −5,0 %, du 2024-03-05 au 2024-05-16, récupéré en 66 jours.
- **Mois :** le pire à −2,9 %, le meilleur à +7,1 %.
- **Exposition :** 5,8 % en moyenne, 33 % au maximum, en position 37 % du temps.

**Limites paper :**
- **Refus :** 10 signaux refusés par le verrou de perte journalière, aucun par le plafond de risque ouvert de 4 %.
- **Définition du verrou :** equity au coût contre equity marquée en début de jour, définition paper. Elle est conservatrice : un gain latent de ≥ 3 % suffit à la déclencher. Ce comportement est donc prudent, il ne gonfle pas le résultat.

## Contrôles effectués

- **Tests `tests/rs/` (27/27)**, conformes à RS-03 §10 :
  - troncature de stratégie sur 4 coupes, à la Freqtrade : signaux, stops, ordres et equity identiques jusqu'à T ;
  - stop monotone, appliqué à `k+1` ;
  - gap sous le stop → sortie à l'open ;
  - sortie de canal à `open(k+1)`, et `open(k+2)` en stress ;
  - pas de réentrée sur la barre de sortie ;
  - taille 0,5 %, plafond 10 %, limite de cash, refus sous 25 %, minimum 10 ;
  - coûts par symbole ;
  - assertion < 2025 ;
  - B0-F sans levier ; B0-E rééquilibré mensuellement.
- **Re-dérivation indépendante des 200 trades** à partir des bougies brutes, par un code séparé du moteur : signal `close > max(high 55 barres précédentes)`, entrée à l'open suivant, stop initial `fill − 3 ATR`, parcours du stop suiveur et du canal, prix de sortie dans la barre. **0 écart.** La somme des P&L égale le capital final moins 5 000 € (+1 642,95 €).
- **Aucune barre ≥ 2025-01-01 lue** : troncature au chargement, assertion dans `simulate`, dernière barre 2024-12-31 20:00.

## Écarts de procédure (à connaître)

- **Pas de revue indépendante avant le run.** RS-03 prévoyait une revue du code par Cursor (rôles inversés) avant le run. Cursor était indisponible (limite mensuelle atteinte) et Samir a demandé à Claude de continuer seul. Garde-fous appliqués à la place :
  - note d'implémentation et code **committés et poussés avant** le run (`cd43489` puis `1a4eba5`) ;
  - re-dérivation indépendante des trades après le run.
  - **Une revue par une autre session reste à faire.** Si elle trouve un défaut, la correction sera documentée et le run rejoué. Ce ne sera pas une variante.
- **Réutilisation de `research_lab/sim.py` (RS-03 §10.5) :** non faite. Voir §10 bis : moteur autonome, aucun changement du paper, du pipeline ni de `sim.py`.

## Suites possibles (décisions de Samir, rien n'est lancé)

1. **Revue indépendante** du code `rs/` et de ce rapport, par une autre session Claude ou par Cursor quand il sera disponible.
2. **Validation 2025 (une seule fois, règles inchangées)** : c'est l'étape prévue par le protocole pour un candidat. Elle consomme la validation 2025 pour cette hypothèse.
3. **Microstructure** (OI / funding / CVD / stablecoins) : seulement après 2, **une variable à la fois**, chacune pré-enregistrée comme nouvelle hypothèse.
4. **Aucun branchement sur le paper ni sur le pipeline** sans validation hors échantillon.
