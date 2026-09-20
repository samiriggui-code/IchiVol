# Étude « IchiVol plus actif » — résultats au 2026-09-20

Complète [AUDIT-PAPER-PERFORMANCE-2026-09-20.md](./AUDIT-PAPER-PERFORMANCE-2026-09-20.md). Paper uniquement : aucun ordre réel, aucun achat, données publiques Binance gratuites. **Rien n'a été déployé** ; la stratégie et les 12 portefeuilles en fonctionnement sont inchangés.

Code : `ichivol-app/engine/research_lab/` (banc de simulation) et `app/paper/{counters,gates}.py` (instrumentation, désactivée par défaut). Manifeste, hachages des données, journaux comptables et transactions : `research_lab/runs/2026-09-20/`.

## 0. Réponse courte

- La stratégie actuelle, rejouée sur bougies clôturées avec exécution prudente, **perd de l'argent net de frais sur toutes les fenêtres** (−36 % sur 8,6 mois de validation, −51 % sur 7 mois de développement). Le brut est proche de zéro : les frais (~20 bps aller-retour) sur ~1 370 transactions de ~1,1 h font le reste.
- Aucune des variantes B (univers élargi) ni C (entrées plus actives) n'améliore ce résultat de façon soutenue (B n'est positive que sur V1, +177 €, et perd −1 221 € sur V3). Plus de transactions = plus de frais.
- La variante de sorties E (tenir la position jusqu'au stop/objectif/changement de direction Ichimoku) montre un **brut positif dans toutes les fenêtres** mais le net n'est positif que sur V1 (et donc sur la validation agrégée, portée par V1) : négatif sur le développement, V2 et V3, et **négatif dans le scénario de coûts défavorable sur presque toutes les fenêtres** (positif seulement sur V1). Résultat insuffisant pour la retenir.
- Recommandation : **conserver la référence en fonctionnement, ne retenir aucune variante, prolonger les tests** (section 9).

## 1. Ce qui explique le peu d'activité (compteurs réels, univers A, barres 1h clôturées)

| Fenêtre | barres | directionnelles (Ichimoku non neutre) | signaux BUY/SELL | runs de signal | runs d'1 seule barre |
|---|---|---|---|---|---|
| Développement 2025-06-01 → 2025-12-31 | 102 720 | 85 420 (83 %) | 2 162 (2,5 %) | 1 643 | 1 223 (74 %) |
| Validation 2026-01-01 → 2026-09-20 | 124 099 | 104 952 (85 %) | 2 172 (2,1 %) | 1 723 | 1 368 (79 %) |

Étages en échec parmi les barres directionnelles (multi-étiquettes : une barre peut échouer à plusieurs étages, ne pas additionner) — développement : régime 82 712 (97 %), location 55 064, participation/RVOL 34 511, structure/MTF 2 748.

Barres où **un seul étage** bloque (ce qu'un assouplissement de cet étage seul pourrait débloquer) — développement : régime 18 063, location 413, RVOL 109, structure 0. Validation : 22 493 / 449 / 64 / 0.

Détail du régime quand il est le seul bloquant (développement) : pas de cassure de range Donchian 5 569, pas de tendance ADX 6 100, volatilité extrême 3 800, régime mort 2 594.

Lecture :
1. **Ce n'est pas un manque de données ni de marchés** sur crypto. C'est **volontaire mais mal calibré** : le filtre de régime (ADX + Donchian + ATR) laisse passer 2,5 % des barres.
2. **Le RVOL protège peu et bloque presque rien** (≤ 109 barres de développement). Assouplir le RVOL n'apporterait quasiment aucune occasion : on ne le touche pas.
3. **Défaut de conception** : le signal d'entrée est une cassure Donchian d'une seule barre, mais la position ne tient que « tant que la décision reste BUY ». 74–79 % des signaux durent 1 barre → détention moyenne 1,1–1,2 h, rotation ~40× le capital par mois.
4. Les instruments : 20 crypto. **TONUSDT n'a plus de bougies Binance depuis le 2026-06-30 02:00 UTC** mais reste dans la liste de surveillance : aucune garde de péremption des données n'existe (aucune position TON n'a été ouverte).
5. La bougie 1h **en formation** est utilisée par la chaîne actuelle (`candles[-1]`, cycle 5 min, MTF sur la bougie 4h en formation). Le code des backtests dit l'inverse (« bougies clôturées »).

## 2. Effet de la bougie clôturée (mesuré, pas supposé)

Reconstruction du comportement ancien (décision toutes les 5 min sur la bougie en formation, exécution au cours du cycle) à partir de klines 5 min publiques, 19 symboles (TON sans données), 14 jours 2026-09-06 → 09-20, mêmes frais et mêmes règles héritées (sans les garde-fous de recherche) :

| Comportement | transactions | brut | net (frais de base) | net (défavorable) | durée moy. | DD max |
|---|---|---|---|---|---|---|
| Ancien (intrabougie, 5 min) | 251 | −53,5 | **−630** | −1 238 | 0,29 h | −14,4 % |
| Mêmes règles, bougies clôturées | 88 | +108,2 | **−104** | −347 | 1,23 h | −6,0 % |

Sur la fenêtre réelle du compte (18/09 19:23 → 20/09 16:00) : ancien 32 transactions, durée 0,30 h ; réel VPS 20 transactions closes, durée 0,33 h. **Validation qualitative seulement** (durées concordantes ; comptes différents car le vrai compte portait 2 positions legacy et des positions confirmées manuellement). Les décisions par cycle du pipeline n'ont jamais été stockées (seulement ouvertures/fermetures) : **les anciennes décisions intrabougie ne sont pas reconstructibles exactement**.

Le passage aux bougies clôturées **réduit la rotation par 3 et les pertes par 6**, mais ne rend pas la stratégie rentable. Il ne « rend » pas plus de gain brut : il supprime des allers-retours qui ne rapportaient pas leurs frais.

## 3. Définition exacte des expériences (fixées avant de voir un résultat)

Communs : 5 000 € virtuels chacun, portefeuilles **indépendants** (pas 15 000 €), mêmes données (hachage dans le manifeste), même modèle d'exécution, mêmes fenêtres, sans levier, sans martingale, sans recherche de paramètres.

Modèle d'exécution (bougies seules, hypothèses documentées) : décision à la clôture de la barre t ; ordre exécuté à l'**ouverture de t+1** ; friction adverse spread + slippage (formule de `paper/risk.py`) intégrée **une seule fois** dans les prix de fill ; commission en jambe séparée ; stop/objectif testés sur les extrêmes des barres **après** l'instant d'entrée ; stop et objectif dans la même barre → **stop d'abord** ; ouverture au-delà d'un niveau → fill à l'ouverture (gap). Frais de base = profil actuel (commission 5 bps, spread 2, slippage 3 par côté). **Défavorable** : commission 10 bps (frais spot standard), spread 4, slippage 8, financement 3 bps/jour sur les shorts.

Limites de risque communes (le comportement actuel : risque 1 %/trade, notionnel ≤ 25 %/ordre, ≤ 5 positions ; le reste **n'existe pas dans le compte actuel** et est ajouté comme **hypothèse de recherche, non validée**) :
- risque cumulé jusqu'aux stops ≤ **4 %** de l'equity (≈ 4 positions à 1 % ; légèrement sous les 5 % implicites) ;
- notionnel agrégé par instrument ≤ 25 % ; une position par instrument ;
- perte journalière ≥ 3 % → plus d'entrée jusqu'au lendemain UTC ;
- un seul trade par « run » de signal (pas de ré-entrée sur le même événement après un stop) ;
- liquidité : ordre ≤ 2 % du volume de la barre d'entrée ; notionnel minimum 10 €.

| | Univers | Règle |
|---|---|---|
| **A référence corrigée** | 20 crypto du catalogue | pipeline actuel, sortie = la décision ne soutient plus la position, garde-fous ci-dessus |
| **B univers élargi** | A + 20 paires USDT | règle A. Sélection **point-in-time** avant la période : volume quotidien médian mai 2025 ≥ 20 M USDT, hors stables/wrapped/leviers, top 20 par volume (jamais par rendement). Biais résiduel : les paires délistées depuis sont absentes |
| **C entrées plus actives** | A | **une** modification : l'exigence de cassure Donchian est suspendue jusqu'à 3 barres clôturées après un vrai signal de même direction, uniquement si elle est le seul étage en échec. Motivation : 74 % des signaux durent 1 barre et c'est la nature « cassure d'une seule barre » du sous-filtre Donchian qui l'explique ; il est le 2e bloquant unique du régime (5 569 barres, derrière ADX 6 100) mais le seul dont l'assouplissement conserve son sens (une cassure récente reste exigée) ; ADX/ATR/location/RVOL/structure inchangés |
| **E sorties** (test séparé) | A | entrées de A ; sortie sur stop/objectif ou changement de direction Ichimoku (le pipeline ne ferme plus la position) |

Période de réglage / validation : les compteurs ci-dessus ont guidé le choix de C sur le **développement** (2025-06-01 → 2025-12-31). Transparence : j'ai aussi affiché les compteurs de validation avant de figer C ; ils sont identiques en structure. La **validation hors échantillon** est 2026-01-01 → 2026-09-20, découpée en trois fenêtres indépendantes (V1 jan–mars, V2 avr–juin, V3 juil–20/09), chacune repartant de 5 000 €.

## 4. Tableau comparatif (frais de base ; DD = drawdown sur clôtures 1h)

| Fenêtre | Var. | Trans. | Brut | Frais (comm. + spread/slip) | **Net** | Espér. nette/trans. | Réussite | Gain moy. / perte moy. | DD max | Expo moy. / max | Durée moy. | Net défavorable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Développement | A | 1 197 | −341 | 2 223 | **−2 564** | −2,14 | 30 % | +8,8 / −6,9 | −52,0 % | 7 % / 103 % | 1,2 h | −3 820 |
| | B | 1 875 | +419 | 3 267 | **−2 848** | −1,52 | 33 % | | −57,5 % | 11 % / 106 % | 1,2 h | −4 265 |
| | C | 1 276 | −779 | 2 123 | **−2 902** | −2,27 | 31 % | | −58,3 % | 11 % / 103 % | 1,8 h | −4 027 |
| | E | 759 | +1 032 | 1 782 | **−750** | −0,99 | 34 % | +38,3 / −21,1 | −24,3 % | 32 % / 103 % | 9,0 h | −2 549 |
| V1 jan–mars | A | 506 | +703 | 1 236 | −533 | −1,05 | 32 % | | −14,4 % | 7 % / 103 % | 1,1 h | −1 694 |
| | B | 789 | +2 225 | 2 048 | **+177** | +0,23 | 35 % | | −9,7 % | 11 % / 102 % | 1,2 h | −1 789 |
| | C | 529 | +904 | 1 329 | −425 | −0,80 | 36 % | | −17,7 % | 11 % / 103 % | 1,8 h | −1 601 |
| | E | 318 | +2 051 | 900 | **+1 151** | +3,62 | 43 % | | −13,2 % | 28 % / 103 % | 7,7 h | +305 |
| V2 avr–juin | A | 429 | −223 | 950 | −1 172 | −2,73 | 25 % | | −24,0 % | 5 % / 102 % | 1,1 h | −2 039 |
| | B | 741 | −354 | 1 538 | −1 892 | −2,55 | 29 % | | −38,5 % | 9 % / 103 % | 1,1 h | −3 010 |
| | C | 447 | −377 | 946 | −1 323 | −2,96 | 26 % | | −27,7 % | 9 % / 102 % | 1,7 h | −2 148 |
| | E | 293 | +313 | 637 | −324 | −1,11 | 31 % | | −21,2 % | 26 % / 102 % | 7,9 h | −938 |
| V3 juil–20/09 | A | 427 | +825 | 1 027 | −202 | −0,47 | 33 % | | −12,8 % | 6 % / 102 % | 1,2 h | −1 235 |
| | B | 739 | +409 | 1 630 | −1 221 | −1,65 | 31 % | | −28,4 % | 11 % / 102 % | 1,2 h | −2 600 |
| | C | 467 | +632 | 1 074 | −442 | −0,95 | 32 % | | −17,6 % | 10 % / 102 % | 1,8 h | −1 545 |
| | E | 287 | +654 | 667 | −13 | −0,04 | 35 % | | −16,3 % | 31 % / 102 % | 8,8 h | −773 |
| **Validation 2026** | A | 1 371 | +972 | 2 789 | **−1 817** | −1,33 | 30 % | +11,5 / −6,9 | −41,4 % | 6 % / 103 % | 1,1 h | −3 580 |
| | B | 2 284 | +1 965 | 4 680 | **−2 714** | −1,19 | 32 % | | −59,8 % | 10 % / 103 % | 1,1 h | −4 435 |
| | C | 1 455 | +953 | 2 928 | **−1 975** | −1,36 | 31 % | | −47,4 % | 10 % / 103 % | 1,7 h | −3 672 |
| | E | 893 | +2 855 | 2 380 | **+475** | +0,53 | 36 % | +41,5 / −22,7 | −30,4 % | 28 % / 103 % | 8,2 h | −1 632 |

Le montant « frais » compte commission **et** spread/slippage (ils sont égaux à 5 bps chacun dans le barème de base ; le spread n'est compté qu'une fois, dans les prix de fill). Le net = brut − frais, vérifié à l'euro près dans chaque exécution (`net_check_gross_minus_costs`).

Différences d'exposition : l'exposition maximale approche 103 % pour toutes les variantes (5 positions × 25 % > capital, donc le cash bloque ; aucun levier). L'exposition **moyenne** diffère fortement : ~6 % (A) contre ~28 % (E). E a donc un risque de marché plus élevé et un drawdown en pourcentage plus proche de A (−30 % contre −41 %) mais avec plus de temps investi. Un gain « supérieur » de E doit être lu avec cette exposition ×4–5.

Causes de sortie (validation) — A : 1 202 changements de signal, 93 stops, 75 objectifs ; E : 524 stops, 314 objectifs, 53 changements de direction.

**Rejets de signaux** (validation A, exclusifs, premier motif défaillant) : plafond de 5 positions 177, cash insuffisant 209, signal déjà traité 49, liquidité 12, plafond de risque cumulé 8, taille minimale 3. Le cash et le plafond de positions sont les limites d'activité côté portefeuille, pas les filtres.

## 5. Sensibilité aux coûts

Résultat net (€, départ 5 000) selon un multiple du barème de base (×0 = sans frais ni friction) :

| | ×0 | ×0,5 | ×1 (base) | ×2 | ×3 |
|---|---|---|---|---|---|
| A développement | −574 | −1 728 | −2 564 | −3 666 | −4 246 |
| E développement | +1 417 | +252 | −750 | −2 235 | −3 371 |
| A validation | +1 412 | −485 | −1 817 | −3 380 | −4 184 |
| E validation | +3 829 | +1 886 | +475 | −1 440 | −2 606 |

E est rentable jusqu'à ~×1,5 les frais de base en validation, mais seulement jusqu'à ~×0,5 en développement. Aucune variante ne résiste au scénario défavorable (E n'est positive que sur V1). Point de réalisme : sur PEPE (prix ~4·10⁻⁶), le pas de cotation 10⁻⁸ vaut ~0,25 % du prix, soit ~12× le spread modélisé (2 bps) : les frais de bas de gamme sont **sous-estimés** pour les paires à très bas prix.

## 6. Dépendance aux meilleures transactions

- **Compte réel VPS (20 transactions)** : PEPE 19/09 (+41,84 €, vérifié : +3,5 % réel de 3,92·10⁻⁶ à 4,06·10⁻⁶ sur klines 1 min) vaut 5× le net (+8,31 €). Sans elle : −33,5 €. Les 3 meilleurs gains = 83 % du gain brut cumulé. Échantillon trop petit pour conclure ; **je ne l'exclus pas**.
- **Simulations (centaines de transactions par fenêtre)** : les 3 meilleurs gains représentent 3–15 % de la somme des gains dans toutes les fenêtres et variantes ; pour E validation, le net sans ses 3 meilleures transactions est +124 € sur +475 €. Le comportement « quelques grands gains » **ne se retrouve pas** dans les fenêtres indépendantes pour A/B/C (résultat dominé par les frais), et pour E il est modéré et n'est pas suffisant pour compenser des fenêtres perdantes (DEV, V2, V3).

## 7. Défauts confirmés, corrections et tests

| # | Défaut (confirmé) | État | Test |
|---|---|---|---|
| 1 | Décision sur bougie 1h et 4h **en formation**, cycle 5 min → signaux qui clignotent (durée moy. 20 min réelle) | Référence de recherche corrigée (bougies clôturées). **Pas implémenté en production** : conception proposée = décision de clôture calculée une fois par bougie et mise en cache, protections surveillées séparément toutes les 5 min | `tests/research_lab/test_signals_causal.py` (préfixe = historique complet) |
| 2 | Position APT `user_confirmed` jamais surveillée : objectif franchi le **2026-09-19 04:15 UTC** (klines 1 min, après l'entrée 20:38:49 ; stop franchi ensuite à 06:19), toujours OPEN | Le correctif est en cours **dans un autre travail** (`app/paper/protection.py`, tick/1 min, marque « à partir de maintenant » pour les positions legacy) : je ne l'ai pas dupliqué. Un de ses tests échoue à l'heure actuelle (`test_legacy_position_is_never_closed_from_history_but_breach_is_reported`). **Position non fermée rétroactivement.** | — |
| 3 | 2 lots NEAR dans le même portefeuille | **Signaux distincts, pas de doublon technique** : lot 1 auto 16:14:14 (3,954), lot 2 `user_confirmed` 16:20:01 (4,064, avec `evidence_id`, clic UI). Unicité par (portefeuille, symbole, TF, **source**) et aucune contrainte en base. Plafond 25 % = **par ordre** (2 462 € = 49 % de l'equity sur NEAR) | `test_one_position_per_symbol…` (garde optionnelle) |
| 4 | Aucun plafond agrégé par instrument, risque cumulé, perte journalière | Garde-fous **optionnels, désactivés par défaut** (`app/paper/gates.py`), activés dans les 3 expériences | `tests/paper/test_protection_gates_counters.py` |
| 5 | Pas de compteurs de rejets | `app/paper/counters.py` (opt-in `log_rejections`) : entonnoir de pipeline (exclusif + multi-étiquette) + motifs de rejet exclusifs | idem |
| 6 | **TON** délisté (2026-06-30) toujours surveillé, pas de garde de péremption | Détecté ; compteur `stale` ajouté ; garde d'exécution **non implémentée** | idem (classification) |
| 7 | Equity des shorts : `positions_value` = notionnel, **latent exclu** ; PnL short réalisé (ratio) ≠ latent (linéaire) | Non corrigé (touche aux chiffres du compte). Aucune position short observée sur le VPS | — |
| 8 | Comparaison des 12 portefeuilles biaisée : dépend du chemin (heure de départ, places prises, positions legacy/manuelles) | Ex. `ICHIVOL_CTX_REGIME` n'a **aucun** blocage (0 ombre) mais son net diffère du baseline (−35,6 vs +8,3) | — |

Portefeuilles apparemment identiques : `ICHIVOL_MS_V1` et `STRUCTURE_CONSENSUS` ont des **paramètres actifs identiques** (mêmes détecteurs, même filtre ; seuls code et libellé diffèrent) → **alias de configuration**, résultats identiques garantis. `ICHIVOL_CTX_RSI` et `ICHIVOL_CTX_FULL` ont des configurations différentes ; les 12 blocages sont tous du RSI (`rsi_overbought_block_long`), OBV n'apparaît que comme motif additionnel sur 3 d'entre eux déjà bloqués → **filtres CMF/OBV/régime sans effet marginal observé** sur cette période, pas un alias. Aucun portefeuille supprimé.

## 8. Comptabilité, reproductibilité et limites

- **Réconciliation du compte réel** : cash 1 291,30 = 5 000 + 8,31 réalisé − 3 715,2 (notionnels ouverts) − 1,86 (frais d'entrée des ouvertes) ; frais des ordres 26,87 = 25,01 (closes) + 1,86 (ouvertes). Cohérent. Le grand livre n'est **pas** en production (aucune table `ledger_*` sur le VPS ; migration `e5f6a7b8c9d0` non appliquée, `paper/broker.py` modifié localement non déployé) : réconciliation par mouvements impossible sur le compte réel.
- **Grand livre dans les simulations** : composant existant `app/brokerage/ledger.Ledger` réutilisé (une seule source de vérité par exécution, clés idempotentes). Solde du journal = cash simulé à ≤ 6·10⁻⁷ € près (arrondi à 8 décimales) sur toutes les exécutions ; commissions du journal = commissions des transactions.
- **Frais** : entrée + sortie, sans minimum (Binance spot n'en a pas). Le barème actuel applique un spread **entier** par côté (au lieu d'un demi-spread) → prudent d'environ 1 bp par côté ; la friction est dans les fills, pas comptée deux fois.
- Non modélisé : exécutions partielles (plafond 2 % du volume, jamais contraignant), pas de cotation et lots Binance, financement des positions longues spot (nul), latence < 1 barre, OI/funding (sans effet sur le statut d'un étage).
- Ichimoku (décalage), pivots de structure et MTF alignés : causalité vérifiée par test de troncature ; HTF = dernière barre 4h **clôturée avant l'ouverture** de la barre 1h (décalage conservateur ≤ 1 barre).
- Univers B : biais de survie résiduel (paires délistées absentes). Sélection sans rendement.
- Simulation temps réel en avant (« forward ») : **à produire** — elle demande un déploiement (décision de clôture + univers élargi), que je n'ai pas fait.

## 9. Recommandation

**Prolonger les tests ; ne retenir aucune variante ; ne pas remplacer la stratégie en fonctionnement.**

1. B et C : rejetées (frais ↑, aucun gain net).
2. E : brut positif partout (1 032 à 3 829 € sans frais sur 7–8 mois), mais la marge est mangée par des frais de ~20 bps sur ~800 transactions. Piste testable **séparément** : réduire le coût par transaction (ordres limites/maker, palier de frais) et la rotation, puis rejouer E sur plusieurs fenêtres. Hors échantillon : gagnante 1 fenêtre sur 3 (V1), perdante V2, ~nulle V3 → insuffisant pour décider.
3. Corriger d'abord la référence (décision sur bougie clôturée, surveillance 5 min réservée aux protections, garde de péremption, verrou par instrument, plafonds agrégés), avec un suivi en avant d'au moins 8 semaines sans retoucher les paramètres.
4. Ne pas conclure sur les +8 € réalisés (ni sur un latent de ~+190 € sur 3 positions) : 20 transactions, une seule explique le net.
5. Étendre au multimarché (forex, métaux, indices) reste l'objectif du projet ; Binance ne remplace pas ce test.

## 10. Addendum — coût par transaction (expérience séparée, mêmes règles, seul le barème change)

Scénarios = **hypothèses**, pas de l'exécution mesurée (`research_lab/run_costs.py`). Net en € sur 5 000 €, frais par côté :

| Barème | Commission / spread / slippage (bps) | E dév. | E V1 | E V2 | E V3 | **E validation** | A validation |
|---|---|---|---|---|---|---|---|
| base (profil paper actuel) | 5 / 2 / 3 | −750 | +1 151 | −324 | −13 | +475 | −1 817 |
| taker standard avec remise BNB | 7,5 / 2 / 3 | −1 113 | +919 | −487 | −183 | −91 | −2 325 |
| ordres limites (maker) | 7,5 / 0 / 1 | −583 | +1 266 | −343 | −7 | +813 | −1 475 |
| palier VIP maker | 2 / 0 / 1 | +432 | +1 806 | +63 | +411 | +2 369 | +173 |

Lectures :
1. **Le barème « base » du profil paper (commission 5 bps) est plus bas que les frais spot Binance réels** (10 bps standard, 7,5 bps avec BNB). Avec 7,5 bps, E devient négative en validation (−91 €). Le compte paper actuel est donc **légèrement flatteur** sur les frais.
2. Les ordres limites ne changent presque rien tant que la commission reste à 7,5 bps ; et ce scénario **ne modélise pas les ordres non exécutés** (sélection adverse), donc il est optimiste.
3. Seul le palier VIP maker (2 bps, sans spread) rend E positive sur les 5 fenêtres — mais ce palier suppose un volume mensuel sans rapport avec un compte de 5 000 €. Conclusion inchangée : E a un brut positif, pas une marge nette réalisable aujourd'hui.
4. Piste restante : réduire la rotation (E fait ~26 aller-retours de capital par mois), à tester séparément.

## 11. Addendum — état de production confirmé par ichivol-49 (lecture du conteneur)

- **Décision sur bougies clôturées en production depuis le 2026-09-20 17:34:36 UTC** (premier cycle ; réglage `DECIDE_ON_CLOSED_CANDLES=True` par défaut, conteneur créé 17:34:07, 0 redémarrage). Avant : comportement intrabougie. Conséquences pour cette étude : (a) toutes les transactions réelles analysées plus haut (sizées, 18/09 → 20/09 16:56) relèvent de **l'ancien** comportement ; (b) le compteur `bar_forming` de l'entonnoir vaut désormais toujours 0 en production ; (c) le suivi en avant de la référence corrigée a **déjà commencé de fait** à 17:34 UTC pour le portefeuille de base : à mesurer séparément de l'historique, sans le mélanger.
- **TONUSDT** : dernière bougie 1h le 2026-06-30 02:00 UTC, `lag_bars=1984`, `stale=True`. Seule `propose_order_intent` refusait la donnée périmée ; ichivol-49 a ajouté la garde à la synchronisation auto et à `POST /paper/positions` (local, testée, **non déployée**).
- **Ordre de release proposé** (`docs/PLAN-RELEASE-ORDONNE-2026-09-20.md`) : C1 compteurs/gardes (mes fichiers, sans effet sur les 12 portefeuilles car aucun profil n'active `log_rejections`), C2 bougies clôturées, C3 chemin d'ouverture, C4 front, C5 grand livre, C6 moniteur de protection ; chaque déploiement D1–D4 exige votre accord explicite, avec sauvegarde et retour arrière ; le VPS reçoit un commit (`git archive`), jamais un rsync de l'arbre de travail.

## 12. Addendum — revue indépendante (ichivol-36) et suites

Rapport complet : `docs/REVUE-SIM-ET-COUTS-ichivol-36-2026-09-20.md`. Recalcul indépendant de A (validation, frais de base) : **identique** (1 371 transactions, brut +971,9, frais 1 394,6, net −1 817,2). Le simulateur est mécaniquement correct ; aucun défaut trouvé ne change le signe des résultats.

Défauts relevés et traitement :
- Plafond de liquidité jugé sur le volume de la barre d'entrée (léger biais) → **corrigé** : barre du signal.
- Une seule graine aléatoire (priorité entre signaux simultanés) → **10 graines** désormais : A validation −1 763 € en moyenne (écart-type 49) ; E validation +784 € (écart-type 268).
- Spread entier par côté (prudent, ≈ +222 € si demi-spread), stops remplis au niveau sans mèche (−74 € à +10 bps), pas de quantification tick/lot, comparaison du grand livre tautologique : **documentés, non corrigés**.
- Barème de coûts par instrument (pas de cotation, spread = 1 tick sur les 19 paires cotées) : frais par côté ≈ 1–3 bps sur les majeures, 7–15 bps sur PEPE, APT, DOT, OP ; effet sur A : −1 817 → −1 605 €. Le palier de slippage est une hypothèse.
- PPO / BEST Cloud en filtre d'entrée : espérance nette par transaction inchangée ; le gain en euros vient de moins de transactions. Usage en sortie non testé.

**Résultat nouveau : les shorts font l'essentiel des pertes** (−1 417 € sur les −1 817 € de A). Le paper actuel ne vend à découvert qu'en simulation, sans financement ; le compte réel n'a observé que des longs. Levier testé **seul**, `allow_short=False`, 10 graines, frais de base (net moyen ; entre parenthèses scénario défavorable) :

| | Dév. | V1 | V2 | V3 | Validation |
|---|---|---|---|---|---|
| A long seul | −1 461 (−2 641) | −143 (−768) | −536 (−1 041) | +438 (−301) | **−310** (−1 898) |
| E long seul | −957 (−1 821) | +437 (+83) | −252 (−579) | +510 (+130) | **+719** (−455) |

A long seul perd 6 fois moins que A ; E long seul est positive en validation avec un drawdown de −16 % (contre −31 %), et reste légèrement positive en défavorable sur V1 et V3. Développement négatif : **toujours pas de raison de retenir E** — c'est la piste la plus prometteuse à suivre en avant, pas une conclusion.

Production : D1 déployé par ichivol-49 après votre accord (commit `fc0674530e`, branche `release/d1-2026-09-20` : compteurs, bougies clôturées, chemin d'ouverture, garde TON). Grand livre (D2), moniteur de protection (D3) et archive LINK (D4) restent en attente de votre accord.

## 13. Addendum — la stratégie sur forex et or (2026-09-21)

Données : Twelve Data, offre gratuite, clé de l'utilisateur, usage de recherche seul (`research_lab/data_td.py`). EUR/USD, GBP/USD, XAU/USD en 1h, ~6,9 mois (2026-02-24 → 2026-09-20), bougies clôturées, sans volume (le RVOL ne peut pas confirmer). Réglages du pipeline inchangés. Fenêtre de développement 15/03 → 15/06, validation 15/06 → 20/09, 5 000 € de départ. **Petit échantillon, aucune décision possible.**

Signaux : BUY/SELL sur ~3 % des bougies (comme en crypto). Résultat net (€) :

| Règle | Fenêtre | Transactions | Frais du profil paper actuel (5 bps comm. + 5 bps friction) | Frais réalistes FX/or (~1,5 bp/côté) | Sans frais |
|---|---|---|---|---|---|
| A | développement | 158 | −345 | −28 | +24 |
| A | validation | 154 | −305 | +3 | +57 |
| E (sortie direction) | développement | 132 | −277 | −22 | +37 |
| E | validation | 132 | −355 | −99 | −52 |
| E longs seuls | dév. / val. | 53 / 66 | −145 / −167 | −38 / −45 | −15 / −26 |

Lectures : (1) **pas d'avantage brut** sur ces marchés (brut entre −52 et +69 €) ; (2) le barème de frais du profil actuel est **trop lourd pour le FX/or** (10 bps par côté) et transforme un résultat nul en −6/−7 % ; avec des frais réalistes le résultat est proche de zéro ; (3) les positions ont un risque minuscule (1–2 € sur EUR/USD) car le plafond de 25 % du capital limite la taille avant le risque de 1 % ; (4) taux de réussite 11–43 % selon le barème. Conclusion : le pipeline peut ouvrir des positions sur ces marchés, mais rien ne montre qu'il y gagne ; à traiter comme une observation, pas comme un test réussi. Un barème de coûts par classe d'actif (hors crypto) serait plus réaliste ; il n'a pas été appliqué au profil en production.
