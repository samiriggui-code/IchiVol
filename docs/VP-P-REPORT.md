# VP-P — Rapport : simulation fidèle du paper et diagnostic

**Protocole :** amendement `VP0-2026-09-27b` (Question P), pré-enregistré au commit `e745f73` **avant** tout run.
**Code :** `ichivol-app/engine/vpp/` + options opt-in de `research_lab/sim.py` (commit `da8dab5`).
**Artefacts :** [`vpp-artifacts/vpp_results.json`](./vpp-artifacts/vpp_results.json) (sha256 des 40 séries, seed, règles, coûts)
et [`vpp-artifacts/vpp_r1_trades.json`](./vpp-artifacts/vpp_r1_trades.json) (2 867 trades de R1, une ligne par trade).
**Données :** Binance Vision spot 1h/4h, 20 cryptos, 2020-09-01 → 2024-12-31. **Rien de 2025 ni de 2026 n'a été téléchargé ou lu.**
**Nature :** diagnostic descriptif. Pas de verdict EDGE, pas de DSR, aucune variante jouée.

---

## En bref

| Question | Réponse |
|----------|---------|
| Le paper actuel fait-il fructifier un capital ? | **Non.** Simulé fidèlement sur 3,5 ans (juil. 2021 → déc. 2024), 5 000 € deviennent **1 876 €** (**−62,5 %**), max drawdown **−64 %**. **Les 7 plis sont négatifs**, en continu comme en réinitialisant le capital à chaque pli. |
| Les pertes sont-elles maîtrisées ? | Chaque perte l'est (≈ 0,2 % du capital par trade), mais elles s'accumulent : 2 867 trades à espérance négative. |
| Est-ce un problème de coûts ? | **Pas seulement.** Avant coûts, le résultat est déjà négatif (−1 146 €). Les coûts (1 978 €) aggravent la perte ; ils ne la créent pas. |
| Est-ce un manque de trades ? | **Non.** 2 867 trades, soit ~820 par an. Le problème est la qualité de chaque trade, pas leur nombre. |
| Où est le problème principal ? | **À l'entrée.** Après un signal BUY, le prix ne monte pas plus que d'habitude pour le même actif (écart ≈ 0). Aucune sortie ne peut transformer un signal sans information en gain. |
| Et la taille des positions ? | Deuxième limite, indépendante : le plafond de 10 % par position est **toujours** atteint. L'exposition moyenne n'est que de **7,9 %** du capital. Même un bon signal ferait progresser le capital très lentement. |

---

## 1. Ce que fait réellement le paper

Détail complet et sources : [`VP-P-PAPER-REEL.md`](./VP-P-PAPER-REEL.md). L'essentiel :

- **Entrée :** pipeline live `BUY` sur bougie 1h close, crypto long seul. Les filtres qui bloquent réellement sont le régime (ATR ni mort ni extrême, ADX en tendance, cassure Donchian), la participation (RVOL faible), la structure (BOS contraire) et l'emplacement (congestion, sous la value area ou l'AVWAP). **Le filtre MTF 4h ne bloque jamais** : il ne fait que passer l'étape en « WATCH ».
- **Sortie :** stop à 1,5 ATR et objectif à 2R, **ancrés sur le prix d'exécution** et surveillés à la minute. Sortie aussi quand la direction Ichimoku n'est plus LONG. Pas de time-stop.
- **Taille :** 0,5 % de risque visé, **plafonné à 10 % du capital par position**. Le stop médian est à 1,83 % du prix, donc 0,5 % de risque demanderait ~27 % du capital par position : **le plafond de 10 % s'applique toujours**, et le risque réel est d'environ **0,2 %** par trade. Au maximum 10 positions, 4 % de risque ouvert cumulé.
- **Coûts :** commission 7,5 bps par côté, plus une friction par symbole (1 bps pour BTC, jusqu'à 14,6 bps pour PEPE).
- **Non reproductible** (documenté) : marchés non-crypto (SPX, NDX, FX, métaux, WTI), scans 15m/4h/1d déclenchés par la navigation dans l'UI, actions manuelles. Sur la première semaine en production, **23 positions sur 43** relèvent de la partie systématique reproduite ici.

**Concordance C1.** Sur 300 barres tirées au hasard, la décision calculée sur la fenêtre live de 299 bougies (avec la direction 4h lue comme en live) est **identique** à celle de la simulation dans **300 cas sur 300**. Limite : l'échantillon ne contient que 3 BUY, donc le contrôle est solide sur les non-BUY et faible sur les BUY.

## 2. Évolution du capital simulé

### 2.1 Parcours continu (R1, run principal) — un seul capital de 5 000 € du 2021-07-01 au 2024-12-31

| Mesure | Valeur |
|--------|--------|
| Capital initial → final | 5 000 € → **1 876 €** |
| Rendement net | **−62,5 %** (CAGR −24,4 %) |
| Max drawdown | **−64,4 %** (pic 2021-07-04 → creux 2024-11-05) |
| Trades | 2 867 · durée médiane **5 h**, moyenne 8,5 h |
| Temps en position | 33 % des heures avec au moins une position |
| Exposition | moyenne **7,9 %** du capital, maximum 100 % (10 positions pleines pendant 65 h au total) |
| Positions simultanées | moyenne 0,8, maximum 10 |
| Taux de réussite | 31,0 % |
| Gain moyen / perte moyenne | +11,84 € / −6,90 € |
| Espérance nette par trade | **−1,09 €** = **−0,17 R** = −0,34 % du notionnel |
| Espérance brute par trade | −0,11 % du notionnel = **−0,04 R** |
| Coûts | commission 1 347 € + friction 632 € = **1 978 €**, soit ~0,13 R ou 0,22 % du notionnel par trade |
| Rejets du portefeuille | `max_positions` 85 · `signal_already_processed` 69 · (SELL ignorés 4 618) |
| Verrou perte journalière | déclenché 1 jour |
| Sensibilité à l'ordre de traitement (seeds 0–4) | −62,6 % à −63,2 % : sans effet |
| Stress coûts adverses (R2) | 5 000 → **971 €** (−80,6 %) |

La place ne manque presque jamais (85 rejets pour 2 867 trades) : **le capital commun n'est pas la contrainte**. Il reste inutilisé à plus de 90 % en moyenne.

### 2.2 Le même parcours découpé par pli (pas de réinitialisation)

| Pli | Capital début → fin | Rendement | DD dans le pli | Trades | Espérance (R) |
|-----|---------------------|-----------|----------------|--------|---------------|
| WF1 2021-S2 | 5 000 → 4 372 | −12,6 % | −14,3 % | 436 | −0,08 |
| WF2 2022-S1 | 4 372 → 3 710 | −15,2 % | −18,3 % | 336 | −0,19 |
| WF3 2022-S2 | 3 710 → 3 306 | −10,9 % | −13,1 % | 316 | −0,22 |
| WF4 2023-S1 | 3 306 → 3 154 | −4,6 % | −14,1 % | 343 | −0,08 |
| WF5 2023-S2 | 3 154 → 2 695 | −14,6 % | −15,6 % | 426 | −0,21 |
| WF6 2024-S1 | 2 695 → 2 103 | −22,0 % | −23,3 % | 446 | −0,28 |
| WF7 2024-S2 | 2 110 → 1 876 | −11,1 % | −16,3 % | 564 | −0,14 |

### 2.3 Plis réinitialisés (R3) — 7 simulations indépendantes de 5 000 € chacune

À lire séparément : **ces 7 résultats ne s'additionnent pas en un portefeuille**.

| Pli | Rendement | Max DD | Trades | Espérance (R) |
|-----|-----------|--------|--------|---------------|
| WF1 | −12,6 % | −14,3 % | 436 | −0,09 |
| WF2 | −14,8 % | −18,0 % | 336 | −0,19 |
| WF3 | −10,7 % | −13,4 % | 317 | −0,22 |
| WF4 | −5,7 % | −14,8 % | 341 | −0,09 |
| WF5 | −14,6 % | −15,6 % | 426 | −0,21 |
| WF6 | −22,2 % | −23,6 % | 440 | −0,29 |
| WF7 | −13,5 % | −16,8 % | 570 | −0,17 |

Marchés haussiers (2021-S2, 2023-S2, 2024) comme baissiers (2022) : tous négatifs.

### 2.4 Par actif (R1)

18 actifs sur 20 sont négatifs. Les deux positifs, OP (+155 €, 116 trades) et TON (+1 €, 13 trades), ne suffisent pas pour y voir un effet.
Pires : DOT −595 €, LINK −346 €, ATOM −323 €, NEAR −302 €. BTC −125 € (204 trades), ETH −9 € (211 trades).

### 2.5 Pont avec VP3 (R4) : BTC, ETH et SOL seuls, même capital commun

5 000 → 4 368 € (−12,6 %), DD −15,4 %, 617 trades, espérance −0,11 R, exposition moyenne **1,8 %**.
La perte est plus faible surtout parce que le capital travaille encore moins. BTC, ETH et SOL sont tous les trois négatifs.

### 2.6 Contexte, pas un verdict

Sur la même période, avec les mêmes coûts d'entrée : conserver du BTC donne +167 % (DD −77 %) ; un panier équipondéré des 14 cryptos disponibles en juillet 2021 donne +80 % (DD −85 %).
Le paper ne se situe pas entre les deux : il perd **et** chute (−64 %).

## 3. Ce qui construit ou détruit la performance

### 3.1 Contribution par motif de sortie (R1)

| Sortie | n | Part | Réussite | Somme nette | Moyenne | MFE moyen | Durée moyenne |
|--------|---|------|----------|-------------|---------|-----------|---------------|
| Objectif 2R | 857 | 30 % | 100 % | **+10 468 €** | +1,89 R | 2,0 R | 10 h |
| Stop | 1 843 | 64 % | 0 % | **−13 144 €** | −1,11 R | 0,57 R | 6,8 h |
| Direction | 167 | 6 % | 19 % | −447 € | −0,39 R | 0,90 R | 19,8 h |

Le paper se comporte en pratique comme un système « stop 1,5 ATR / objectif 3 ATR » en 1h : la sortie sur changement de direction ne concerne que 6 % des trades.
Avec un objectif à 2R, il faudrait gagner plus de 33 % des trades **avant coûts** pour être à l'équilibre. Le paper en gagne 30 %, ce qui correspond à peu près à un tirage au hasard entre les deux niveaux.

### 3.2 Entrées — le mouvement attendu se produit-il ?

**Rendement après l'entrée, comparé à la dérive normale des mêmes actifs** (moyenne sur toutes les heures) :

| Horizon | Moyenne après BUY | Médiane | Part > 0 | Dérive normale | Écart |
|---------|-------------------|---------|----------|----------------|-------|
| 1 h | −0,01 % | −0,11 % | 44 % | +0,01 % | −0,01 pt |
| 4 h | +0,08 % | −0,15 % | 46 % | +0,03 % | +0,05 pt |
| 12 h | +0,11 % | −0,26 % | 45 % | +0,08 % | +0,03 pt |
| 24 h | +0,22 % | −0,35 % | 46 % | +0,16 % | +0,06 pt |
| 48 h | +0,57 % | −0,18 % | 48 % | +0,33 % | +0,24 pt |

**Lecture.** À 1–24 h, horizon où se jouent 90 % des trades, le signal BUY ne prédit pas mieux que le hasard : les écarts (≤ 0,06 point) sont bien en dessous du coût d'un aller-retour (0,22 %). La médiane est négative et moins d'une entrée sur deux est suivie d'une hausse.
À 48 h, l'écart moyen (+0,24 pt) dépasse à peine le coût. Il est porté par quelques fortes hausses (la médiane reste négative) et n'a **pas d'intervalle de confiance** : il ne prouve rien.

**Retard ?** Au signal, le prix a déjà monté d'en moyenne **2,2 R en 12 barres** (3,0 R en 24), c'est-à-dire d'environ 3,4 ATR. L'entrée arrive donc après une cassure (Donchian + ADX), ce qui est cohérent avec la construction du pipeline.
En revanche, **les entrées les plus tardives ne sont pas les pires** : par tiers de hausse pré-signal, l'espérance est de −0,23 R (hausse faible), −0,17 R (moyenne) et −0,12 R (forte). Le retard ne suffit donc pas à expliquer les pertes.

**Contextes des pertes** (descriptif, aucun test) :
- **Alignement 4h :** −0,13 R si aligné, −0,22 R si opposé. Comme le filtre MTF ne bloque jamais, ces trades opposés sont bien pris.
- **RVOL :** −0,23 R dans le tiers faible, −0,07 R dans le tiers fort.
- **Durée :** trades de moins de 4 h : −0,36 R (1 153 trades) ; trades de plus de 24 h : +0,20 R. Attention, ce dernier chiffre n'est pas exploitable : un trade dure longtemps *parce qu'il* n'a pas touché son stop.

### 3.3 Sorties — excursions et part conservée

- **MFE médian 0,85 R.** Seuls 46 % des trades atteignent +1 R, et 22 % atteignent l'objectif de +2 R.
- **MAE médian 1,0 R.** La moitié des trades touche le stop.
- **Part conservée.** Sur l'ensemble, le gain brut réalisé ne représente que 4 % des MFE cumulés. Pour les gagnants, la médiane est de 100 % (l'objectif est atteint, donc tout est pris).

### 3.4 Les cinq situations demandées (R1, 2 867 trades, drapeaux non exclusifs)

| Code | Situation | Trades | % | Somme nette | Lecture |
|------|-----------|--------|---|-------------|---------|
| F1 | Entrée suivie d'un mouvement défavorable (MFE < 0,5 R) | **1 083** | **38 %** | **−7 308 €** | **Première source de pertes** : plus d'un trade sur trois ne va jamais dans le bon sens |
| F2 | Gain favorable puis rendu (MFE ≥ 1 R, brut ≤ 0) | 447 | 16 % | −3 132 € | Montés à +1 R, finis au stop |
| F3 | Sortie suivie d'une poursuite (≥ +1 R dans les 24 h, hors stop) | 688 | 67 % des sorties hors stop | +6 713 € | Voir la mise en garde ci-dessous |
| F4 | Stop touché avant un rebond (≥ entrée + 1 R dans les 24 h) | 690 | 37 % des stops | −4 769 € | 371 de ces trades sont aussi F1 |
| F5 | Positif avant coûts, négatif après | 12 | 0,4 % | −4 € | Négligeable : les coûts ne transforment presque jamais un gain en perte |

**Mise en garde sur F3 et F4.** Dans les 24 h qui suivent **n'importe quelle** sortie, le plus haut dépasse le prix de sortie d'environ 2 R en moyenne : +2,0 R après un stop, +2,6 R après un objectif, +1,8 R après une sortie direction. Le prix de clôture 24 h plus tard, lui, n'est qu'à +0,1 à +0,3 R. Autrement dit, « le prix est repassé au-dessus » est la respiration normale d'un actif crypto sur 24 h, pas le signe d'une sortie mal placée.
F3 et F4 **ne montrent donc pas** que l'objectif serait trop proche ou le stop trop serré. Ils montrent que ces niveaux sont à l'intérieur du bruit horaire.

### 3.5 Filtres (518 415 heures éligibles)

- Un BUY n'apparaît que sur **0,9 %** des heures (4 733). **Le régime est la première cause de non-BUY dans 95,6 % des heures.**
- Parmi les heures où Ichimoku est LONG (218 780), l'étape en échec est :

| Étape | Échec (les étapes se recouvrent) | Seule étape en échec |
|-------|----------------------------------|----------------------|
| Régime | 97,3 % | 21,5 % |
| Location | 65,8 % | 0,4 % |
| Participation | 37,4 % | 0,1 % |
| Structure | 2,9 % | ~0 % |

- Motifs du régime parmi ces heures LONG : pas de tendance ADX 33,0 %, pas de cassure Donchian 28,8 %, ATR mort 17,8 %, ATR extrême 17,7 %.
- Une fréquence de blocage élevée **ne dit pas** qu'un filtre est mauvais. Avec un signal d'entrée sans pouvoir prédictif, laisser passer plus de trades multiplierait surtout les coûts : ce rapport ne recommande **pas** d'assouplir un filtre.

## 4. Ce qui reste incertain

1. **La partie non systématique du paper n'est pas simulée** : marchés non-crypto, scans 15m/4h/1d lancés depuis l'UI, décisions manuelles. Elle représentait 20 positions sur 43 la première semaine. Le verdict ci-dessus porte sur le cœur crypto 1h.
2. **Surveillance à la minute contre barres 1h.** Le simulateur applique « stop d'abord » quand une barre touche les deux niveaux. C'est arrivé **2 fois sur 2 867** : impact négligeable. Le décalage d'exécution de 0 à 5 minutes après la clôture n'est pas modélisé.
3. **Univers choisi en 2026 (survivants).** Ce biais favorise normalement la stratégie ; il ne peut pas expliquer une perte.
4. **Période de développement seulement** (2021-S2 → 2024). 2025 et 2026 ne sont pas vus, volontairement.
5. **C1 compte seulement 3 BUY.** Une concordance ciblée sur les barres BUY renforcerait la preuve de fidélité (mesure listée ci-dessous).
6. **Aucun chiffre ci-dessus n'a d'intervalle de confiance.** La conclusion « perte sur chaque pli, avec les deux profils de coûts et quel que soit l'ordre de traitement » est robuste. Les écarts fins (tiers de RVOL, alignement 4h, +0,24 pt à 48 h) ne le sont pas.

## 5. Le prochain changement précis à tester

**Constat qui motive le test.** Le problème observé est le **contenu d'information du signal d'entrée**. Aux horizons de détention actuels, il ne fait pas mieux que la dérive normale. Modifier les sorties (trailing, time-stop, objectif plus loin) ne ferait que remodeler la distribution des gains et pertes d'un signal sans pouvoir prédictif. La sortie « direction », elle, ne concerne que 6 % des trades.
Un seul indice va dans l'autre sens : l'écart grandit avec l'horizon (+0,24 pt à 48 h). Il n'est pas prouvé.

**Mesure manquante, à pré-enregistrer avant tout nouveau changement de stratégie (proposition P3) :**
une **étude d'événement** sur les barres BUY du pipeline, restreinte aux plis de développement. Elle compare le rendement après BUY au rendement de barres **tirées au hasard dans le même actif et le même mois**, aux horizons 24, 48, 96 et 168 h, avec un intervalle de confiance par bootstrap en blocs. La question est binaire :

- **Si aucun horizon n'a un écart dont l'intervalle exclut 0 et qui dépasse le coût d'un aller-retour :** l'entrée B7 n'a pas d'information exploitable. On arrête d'optimiser ce signal et on garde le paper uniquement comme témoin.
- **Si un horizon H passe :** un seul test de stratégie, pré-enregistré. Mêmes entrées, pas d'objectif 2R, sortie à H ou sur changement de direction, stop inchangé. Il serait jugé sur le parcours continu, en capital commun.

**Deuxième chantier, indépendant du premier : la taille.** Avec le plafond de 10 % par position, l'exposition moyenne n'est que de 7,9 %. Même une entrée rentable ne ferait croître le capital que très lentement. Cela ne change rien aujourd'hui (on ne grossit pas des positions perdantes), mais ce plafond devra être revu **si et seulement si** P3 trouve de l'information.

**Le bouclier (BN) reste une expérience séparée.** S'il est validé, il répondra à la question « moins de chute que B0 », pas à celle de la rentabilité du paper.

**Paper live.** Rien n'est à changer tant qu'aucun test ne l'a justifié. Pour qu'il mesure vraiment la stratégie, il faudrait que les scans UI 15m/4h/1d ne puissent plus ouvrir de positions automatiques. Ce serait une décision de Samir : c'est un changement de comportement du produit, pas de stratégie.
