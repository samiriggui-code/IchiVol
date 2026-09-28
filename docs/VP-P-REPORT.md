# VP-P — Rapport v2 : paper fidèle, contrôles de fidélité et étude d'événement

**Version :** v2 (2026-09-28). Elle remplace la v1 (commit `8afcd5b`), conservée dans [`vpp-artifacts/v1/`](./vpp-artifacts/v1/) avec ses résultats bruts. Les changements v1 → v2 sont listés au §8.
**Protocole :**
- amendement `VP0-2026-09-27b` (Question P), pré-enregistré au commit `e745f73` ;
- amendement `VP0-2026-09-28` (contrôles C2/C3, tolérance ε, intervalles, étude P3), pré-enregistré au commit `d218df4`.

Les deux sont antérieurs aux runs qu'ils décrivent.

**Données :** Binance Vision spot 1h/4h, 20 cryptos, 2020-09-01 → 2024-12-31. **Rien de 2025 ni de 2026 n'a été téléchargé ou lu.**
**Artefacts** ([`vpp-artifacts/`](./vpp-artifacts/)) :
- `vpp_results.json` : R1–R4, C1, filtres, contexte ;
- `vpp_r1_trades.json` et `vpp_r4_trades.json` : journaux de trades ;
- `vpp_fidelity_c2.json` et `vpp_fidelity_c3.json` : contrôles de fidélité ;
- `vpp_p3_event_study.json` : étude d'événement ;
- `vpp_p3_posthoc_momentum.json` : contrôle post-hoc.

**Convention de lecture :** chaque résultat est marqué **[Mesuré]**, **[Interprétation]** ou **[À tester]**. Les intervalles viennent d'un bootstrap par mois calendaire (des mois entiers tirés, tous actifs confondus, 10 000 tirages, seed 7).

---

## Réponses courtes

| Question | Réponse |
|----------|---------|
| La simulation reproduit-elle suffisamment le cœur paper étudié ? | **Oui, pour le cœur automatique crypto 1h**, sur les trois critères pré-enregistrés. Décisions : 100 % d'accord sur 552 BUY, 150 cas proches d'un seuil et 150 cas « un seul filtre bloquant ». Cycle complet à travers le **vrai moteur paper** : 100 % sur deux fenêtres, 97,5 % sur la fenêtre où le capital commun est saturé. **Hors périmètre :** marchés non-crypto, scans de l'interface, actions manuelles, surveillance à la minute. |
| Quels résultats restent confirmés ? | La perte du parcours simulé (5 000 → 1 876 €, 7 plis négatifs) et l'espérance nette négative par trade (**−0,17 R, IC 95 % [−0,24 ; −0,10]**). **Nuance v2 :** le résultat **brut** par trade (−0,11 % du notionnel) a un IC qui **contient 0** : ce sont les coûts qui rendent la perte certaine. L'écart « 857 objectifs contre 22 % à 2R » était une erreur de comparaison flottante, corrigée : les deux chiffres valent 29,9 %. |
| Les BUY apportent-ils un avantage mesurable aux horizons étudiés ? | **Non, pas d'avantage établi.** Après un début de série BUY, le rendement est en moyenne **inférieur** à celui de barres tirées au hasard dans le même actif et le même mois, à 24, 48, 96 et 168 h (−0,29 à −0,98 point). Au niveau de décision corrigé pour 4 horizons, aucun intervalle n'exclut 0 dans un sens ni dans l'autre. En revanche, un avantage moyen **supérieur à +0,01 pt (24 h) et +0,13 pt (96 h)**, plus petit que le coût d'un aller-retour (0,22 %), **est exclu**. |
| Quel unique changement mérite ensuite un test ? | **Aucun changement de l'entrée B7** (filtres, sorties, tailles) sur cette base : l'optimisation de cette entrée est **suspendue**, comme pré-enregistré. La seule piste cohérente avec ce qui a été mesuré est déjà pré-enregistrée à part : **BN** (bouclier régime, PR #157). Elle ne jugera que le couple chute/rendement face à B0, pas la qualité des entrées paper (§7). |

---

## 1. Fidélité de la simulation

### 1.1 Ce qui est simulé [Mesuré dans le code et la base de prod, cf. [`VP-P-PAPER-REEL.md`](./VP-P-PAPER-REEL.md)]

- **Entrées :** pipeline live `BUY` sur bougie 1h close, crypto, long seul.
- **Sorties :** stop à 1,5 ATR et objectif à 2R, ancrés sur le prix d'exécution ; sortie au changement de direction Ichimoku ; pas de time-stop.
- **Taille :** 0,5 % de risque, plafond de 10 % par position, 10 positions, 4 % de risque ouvert, capital commun de 5 000 €.
- **Coûts :** 7,5 bps de commission + friction propre à chaque symbole.

### 1.2 C1 et C2 — décisions et valeurs déterminantes [Mesuré]

On compare le calcul « comme en live » (299 bougies 1h closes, 299 bougies 4h closes à l'instant de décision) au calcul sur l'historique complet utilisé par le simulateur.

| Échantillon (seed 7) | n | Actifs / années | Décision | Direction, régime ATR, force ADX, Donchian, niveau RVOL | ATR et distance de stop | Statut « structure » |
|----------------------|---|-----------------|----------|---------------------------------------------------------|-------------------------|----------------------|
| C1 aléatoire | 300 | tous | 100 % | — | — | — |
| **C2-BUY** (≤ 8 par actif × année) | **552** | 20 / 2021–2024 | **100 %** | 100 % | **identiques** (écart max 0) | 97,8 % |
| C2-SEUIL (proche d'un seuil, tiré dans 52 071 cas) | 150 | 20 / 2021–2024 | 100 % | 100 % | identiques | 100 % |
| C2-SEUL (le régime est le seul filtre bloquant) | 150 | 20 / 2021–2024 | 100 % | 100 % | identiques | 98,7 % |

- **Désaccords :** 0 dans chaque sens (0 BUY présent seulement dans le simulateur, 0 BUY présent seulement en live).
- **Cohérence interne :** les valeurs recalculées pour ce contrôle redonnent exactement les décisions du simulateur (0 écart).
- **Seul écart :** le statut de l'étape « structure » (1 à 2 % des cas). Il vient du décalage d'une heure de l'étiquette 4h. Cette étape ne passe alors qu'en WATCH, **jamais en échec** : la décision n'est pas touchée.
- **Limite :** C2 compare deux méthodes de calcul sur les **mêmes** données. Il ne compare ni la source de données (Vision contre REST live), ni l'instant réel d'exécution.

### 1.3 C3 — cycle complet et capital commun à travers le vrai moteur paper [Mesuré]

Les décisions du simulateur sont rejouées dans `app.paper.engine.sync_position`, la même fonction que la production. Elle exerce Risk Kernel, taille, ouverture, sortie stop/objectif/direction et comptabilité. Le rejeu se fait sur un portefeuille jetable de la base de dev ; les protections dans la barre passent par `resolve_bar_exit` + `close_capital_position`.

| Fenêtre (14 jours, 5 000 €) | Trades sim / moteur | Identiques (entrée, quantité ±0,5 %, sortie) | Écart max. quantité / stop | Écart max. P&L d'un trade | Equity finale |
|-----------------------------|--------------------|----------------------------------------------|----------------------------|---------------------------|---------------|
| W-a 2021-07-01 | 26 / 26 | **26 (100 %)** | 0 / 0 | 4·10⁻¹⁴ € | identique |
| W-b 2024-01-01 | 44 / 44 | **44 (100 %)** | 0 / 0 | 5·10⁻¹⁴ € | identique |
| W-c 2024-09-07 (plafond de 10 positions atteint) | 81 / 81 | **79 (97,5 %)** | 1,2 % / 0 | 0,15 € | écart 0,0015 % |

- **Les 2 écarts de W-c** viennent de l'ordre de traitement quand le cash manque :
  - le simulateur décide à la clôture puis exécute toutes les entrées à l'ouverture ;
  - le moteur traite les actifs un par un à l'ouverture, comme en live.

  D'où une entrée XRP décalée d'une barre (le moteur la refuse d'abord pour cash insuffisant) et une taille SUI plus petite de 1,2 %. Impact : négligeable. Le plafond de 10 positions n'est atteint que **65 heures sur 3,5 ans**.
- Les compteurs de SELL ignorés diffèrent légèrement (journalisation seulement, aucun effet sur les trades).
- **Critères pré-enregistrés** (≥ 98 % sur les BUY, ≥ 95 % sur les cas limites, ATR < 0,1 %, ≥ 95 % de trades identiques, cash ±1 %) : **tous remplis**. Aucune correction du simulateur n'a été nécessaire, donc R1–R4 n'ont pas eu à être rejoués pour une raison de fidélité.
- **Limites de C3 :** le verrou de perte journalière est désactivé des deux côtés (il lit l'horloge système ; 1 seul déclenchement dans R1). Les protections sont évaluées sur barres 1h des deux côtés : C3 valide la comptabilité, les gates et la taille, **pas** la surveillance à la minute.

### 1.4 Toujours hors périmètre [Mesuré en production, non simulable]

- Marchés non-crypto, scans 15m/4h/1d lancés depuis l'interface, décisions manuelles : 20 positions sur 43 la première semaine. Les scans de l'interface sont traités par la PR séparée #161.
- Exécution réelle 0 à 5 minutes après la clôture.
- Mémoire « une entrée par série » perdue au redémarrage.

## 2. Réconciliation « 857 objectifs » contre « 22 % à 2R » [Mesuré]

- **Cause :** comparaison flottante. Un trade sorti à l'objectif a un MFE de 1,99999999999995 à 2,00000000000004 R. Le test strict `MFE ≥ 2` en écartait 217 sur 857.
- **Correction** (Q.1, pré-enregistrée) :
  - tolérance ε = 10⁻⁹ R sur tous les seuils en R ;
  - mouvements en R mesurés depuis le prix d'exécution, qui sert d'ancrage au stop et à l'objectif.
- **Résultat :** 29,9 % des trades atteignent 2R, soit **exactement** les 857 sorties à l'objectif.
- **Effets secondaires :**
  - F4 passe de 690 à 679 (référence « entrée + 1R » prise au prix d'exécution) ;
  - la part conservée agrégée passe de 4,2 % à 2,4 % ;
  - F1, F2, F3, F5 et toutes les mesures de capital sont inchangés.

## 3. Capital simulé — résultats confirmés

### 3.1 Parcours continu R1 (5 000 €, 2021-07-01 → 2024-12-31, 20 cryptos) [Mesuré]

| Mesure | Valeur | IC 95 % (bootstrap mensuel) |
|--------|--------|-----------------------------|
| Capital final | **1 876 €** (−62,5 %, CAGR −24,4 %) | — |
| Max drawdown | −64,4 % | — |
| Trades | 2 867 · durée médiane 5 h · taux de réussite 31,0 % | — |
| Espérance nette / trade | −1,09 € | **[−1,51 ; −0,68]** |
| Espérance nette / trade en R | −0,17 R | **[−0,24 ; −0,10]** |
| Résultat brut / trade (% du notionnel) | −0,11 % | **[−0,25 ; +0,03]** : contient 0 |
| Coûts / trade | 0,22 % du notionnel (~0,13 R) | — |
| Exposition moyenne / temps en position | 7,9 % / 33 % des heures | — |
| Sensibilité à l'ordre (seeds 0–4) · coûts adverses (R2) | −62,6 % à −63,2 % · −80,6 % | — |

Les **7 plis sont négatifs**, en parcours continu (−4,6 % à −22,0 % par pli) comme avec un capital réinitialisé à chaque pli (R3 : −5,7 % à −22,2 % ; ces 7 résultats indépendants ne s'additionnent pas). 18 actifs sur 20 sont négatifs.
R4 (BTC, ETH et SOL, capital commun) : 5 000 → 4 368 € (−12,6 %), espérance −0,11 R, IC [−0,235 ; +0,002].

[Interprétation]
- La perte nette de la combinaison testée (cette entrée, ces sorties, ces tailles, ces coûts) est établie.
- Avant coûts, le résultat par trade n'est **pas distinguable de zéro**. La v1 disait « déjà négatif avant coûts » : c'était vrai du point estimé, pas établi statistiquement. Avec ~820 trades par an, les coûts (0,22 % par aller-retour) suffisent à rendre la perte certaine.
- Le capital commun n'est pas la contrainte : il reste inutilisé à plus de 90 % en moyenne. Le plafond de 10 % limite la croissance possible, mais le relever n'apporterait aucun avantage tant que l'espérance est négative : **aucun changement de taille n'est proposé**.

## 4. Entrées [Mesuré, puis Interprétation]

- **Contre la dérive moyenne du même actif** (comparaison v1, reprise avec IC) : les écarts à 1, 4, 12, 24 et 48 h valent −0,01 / +0,05 / +0,03 / +0,06 / +0,24 point, et **tous les IC 95 % contiennent 0** (par exemple 24 h : [−0,29 ; +0,41]).
- **Contre des témoins du même actif et du même mois** (P3, référence pré-enregistrée, §6) : l'écart devient **négatif** à tous les horizons.
  - **[Interprétation] :** les BUY tombent surtout pendant des mois haussiers. Comparés à la moyenne de toute la période, ils semblent légèrement meilleurs ; comparés au même mois, ils font moins bien qu'une entrée au hasard.
- **Retard :** au signal, le prix a déjà monté de 2,2 R en 12 barres. Les entrées les plus tardives ne sont pas les pires (espérance −0,23 / −0,17 / −0,12 R du tiers de hausse faible au tiers de hausse forte).
  - **[Interprétation] :** le retard seul n'explique pas les pertes.
- **Contrôle post-hoc**, non pré-enregistré et hors décision, demandé par la revue RS : on prend comme témoins des barres qui ont **aussi** monté de plus de 2 R en 12 barres. L'écart reste négatif (24 h −0,21 [−0,47 ; +0,05] ; 48 h −0,42 [−0,79 ; −0,06] ; 96 h −0,45 [−1,02 ; +0,11] ; 168 h −0,28 [−0,94 ; +0,41]).
  - **[Interprétation] :** les filtres B7 n'ajoutent rien de mesurable à un simple mouvement haussier récent ; à 48 h, ils font même moins bien.
- **Contextes** (tiers de RVOL, alignement 4h) : les écarts d'espérance (−0,07 à −0,26 R) sont descriptifs et sans IC. Ce ne sont **pas** des résultats établis.

## 5. Sorties [Mesuré, puis Interprétation]

| Sortie | n | Somme nette | Moyenne | MFE moyen |
|--------|---|-------------|---------|-----------|
| Objectif 2R | 857 (30 %) | +10 468 € | +1,89 R | 2,0 R |
| Stop | 1 843 (64 %) | −13 144 € | −1,11 R | 0,57 R |
| Direction | 167 (6 %) | −447 € | −0,39 R | 0,90 R |

- MFE médian 0,85 R ; 46,3 % des trades atteignent +1 R, 29,9 % atteignent +2 R.
- Situations (non exclusives) :
  - **F1** (jamais au-delà de +0,5 R) : 1 083 trades, −7 308 € ;
  - **F2** (+1 R atteint puis brut ≤ 0) : 447 trades, −3 132 € ;
  - **F3** (≥ +1 R après une sortie hors stop) : 688 trades ;
  - **F4** (≥ entrée + 1 R après un stop) : 679 trades, −4 679 € ;
  - **F5** (positif avant coûts, négatif après) : 12 trades.
- Mise en garde conservée : dans les 24 h qui suivent **toute** sortie, le plus haut dépasse le prix de sortie d'environ 2 R en moyenne ; la clôture 24 h plus tard n'est qu'à +0,1 à +0,3 R. F3 et F4 décrivent l'amplitude normale des mouvements sur 24 h. Ce ne sont pas des preuves de niveaux mal placés.

[Interprétation, reformulée par rapport à la v1]
- Les sorties testées (1,5 ATR / 2R / direction) ne transforment pas ces entrées en gain.
- Cela **ne démontre pas** qu'aucune autre gestion des sorties le pourrait. Par exemple, une sortie qui laisse courir profite de la dérive haussière et des queues épaisses du marché (le buy & hold BTC en est le cas limite).
- Mais P3 montre qu'à entrée égale dans le mois, des barres prises au hasard font mieux : une telle sortie capterait surtout la dérive du marché, pas un avantage du signal.
- **[À tester, séparément] :** ce qui relève de l'exposition au régime, pas du déclencheur B7 → c'est l'objet de BN (§7).

## 6. Étude d'événement P3 (pré-enregistrée, amendement `VP0-2026-09-28` Q.5)

**Méthode :**
- **Événement :** début de série BUY (3 686 événements).
- **Rendement :** de l'ouverture suivante à la clôture `t+h`, brut.
- **Témoins :** 20 barres tirées au hasard dans le même symbole et le même mois.
- **Intervalles :** bootstrap par mois (dépendance entre actifs et chevauchements) ; décision au niveau Bonferroni 98,75 % pour 4 horizons.
- **Coûts :** aller-retour paper du symbole (0,22 % en moyenne) ; stress adverse.

### 6.1 Résultat principal [Mesuré] — moyennes en %, entre crochets l'IC 98,75 % (IC 95 % pour information)

| h | Après BUY (médiane) | Témoins | Différence d | Net hypothétique (coûts paper) | Net adverse |
|---|---------------------|---------|--------------|--------------------------------|-------------|
| 24 | +0,14 (−0,36) | +0,44 | **−0,29** [−0,60 ; +0,01] (95 % : −0,53 ; −0,06) | −0,08 [−0,55 ; +0,40] | −0,32 [−0,79 ; +0,16] |
| 48 | +0,50 (−0,23) | +0,85 | **−0,35** [−0,97 ; +0,27] (−0,85 ; +0,14) | +0,28 [−0,70 ; +1,32] | +0,04 [−0,94 ; +1,08] |
| 96 | +1,10 (−0,11) | +1,74 | **−0,64** [−1,40 ; +0,13] (−1,26 ; −0,02) | +0,87 [−0,84 ; +2,79] | +0,63 [−1,08 ; +2,55] |
| 168 | +2,04 (−0,04) | +3,03 | **−0,98** [−2,24 ; +0,24] (−1,97 ; −0,02) | +1,82 [−1,48 ; +5,39] | +1,58 [−1,72 ; +5,15] |

**Deux questions distinctes :**
- **Surperformance des témoins (A) :** non établie à aucun horizon. Le point estimé est **négatif** partout ; à 95 % (sans correction), l'IC exclut 0 **du côté négatif** à 24, 96 et 168 h.
- **Rentabilité nette hypothétique (B) :** non établie à aucun horizon. La moyenne devient positive à partir de 48 h, mais les médianes restent négatives et les IC contiennent largement 0. **[Interprétation]** Ce positif moyen est la dérive haussière du marché : les témoins gagnent davantage.

Même tableau pour toutes les barres BUY (4 733) et pour les entrées réellement exécutées dans R1 (2 867) : même profil. Pour les entrées exécutées, à 168 h, d = −1,10 avec un IC 98,75 % [−2,21 ; −0,06] qui **exclut 0** : ces entrées font moins bien que le hasard du même mois.
Par année, d à 48 h : 2021 −1,15 ; 2022 −0,14 ; 2023 −0,47 ; 2024 −0,04. Aucune année ne montre d'écart positif (descriptif, sans IC).

### 6.2 Décision (règle pré-enregistrée) et ce que l'étude permet d'exclure

- **Aucun horizon favorable (A et B).** L'optimisation de l'entrée B7 est **suspendue sur cette base**.
- **Exclu** (niveau 98,75 %) : un avantage moyen supérieur à **+0,01 pt** à 24 h, **+0,27 pt** à 48 h, **+0,13 pt** à 96 h et **+0,24 pt** à 168 h.
  - À 24 et 96 h, un avantage assez grand pour payer un aller-retour (0,22 %) est donc exclu.
  - À 48 et 168 h, un avantage de l'ordre du coût d'un aller-retour n'est pas exclu, mais il ne suffirait pas à rendre la stratégie rentable.
- **Non exclu :**
  - un petit avantage en dessous de ces bornes ;
  - un avantage limité à un sous-ensemble (un actif, une période, un contexte) : l'étude n'a pas la puissance pour le voir, et le chercher serait une recherche de paramètres ;
  - un autre usage des mêmes informations (autre univers, autre unité de temps, autre gestion de l'exposition).

## 7. Le seul changement qui mérite un test

**Pas de test sur l'entrée B7, ses filtres, ses sorties ou ses tailles.** La règle pré-enregistrée le suspend. De plus :
- relever le plafond de 10 % ou assouplir un filtre augmenterait une exposition à espérance négative ;
- ajouter un indicateur répondrait à un problème qui n'est pas identifié.

**La seule hypothèse cohérente avec ce qui a été mesuré** est que la valeur observée vient de la **dérive du marché** (les témoins du mois gagnent) et non du déclencheur. Elle est **déjà pré-enregistrée** : **BN**, être investi tant que la direction HTF close n'est pas baissière (amendement `VP0-2026-09-27`, PR #157, étape 2 après les corrections S1-R1/S1-R2). Son verdict « bouclier » portera sur la chute et le rendement face à B0. **Il ne dira rien de la rentabilité du paper ni de la qualité de ses entrées et sorties.**

Côté paper live :
- il continue inchangé, comme témoin ;
- la PR #161 empêche la navigation dans l'interface d'y créer des positions, ce qui rendra la mesure du cœur 1h plus propre ;
- son déploiement reste une décision de Samir.

## 8. Changements v1 → v2

| Élément | v1 | v2 | Raison |
|---------|----|----|--------|
| Part des trades atteignant 2R | 22,3 % | **29,9 %** (= sorties à l'objectif) | comparaison flottante (Q.1) |
| F4 | 690 | 679 | référence prise au prix d'exécution (Q.1) |
| Part conservée agrégée | 4,2 % | 2,4 % | idem |
| « Brut déjà négatif » | affirmé | **IC [−0,25 ; +0,03] % : non établi** | intervalles (Q.4) |
| « Le signal ne prédit pas mieux que le hasard » | affirmé | « aucun avantage établi ; contre témoins du même mois, écart négatif ; bornes exclues au §6.2 » | P3 + IC |
| « Aucune sortie ne peut transformer un signal sans information en gain » | affirmé | limité aux sorties testées (§5) | formulation trop absolue |
| Capital, trades, plis, R2–R4 | — | **identiques** | le simulateur n'a pas changé |
| Nouveaux | — | C2, C3, P3, IC, post-hoc momentum | amendement `VP0-2026-09-28` |
