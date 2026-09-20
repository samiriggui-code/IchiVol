# Revue indépendante de `research_lab/sim.py`, recalcul de A, barème de coûts, test PPO / BEST Cloud

**Auteur :** session ichivol-36 (lab) · **Date :** 2026-09-20 · **Périmètre :** lecture seule de `research_lab/*`, aucun fichier de `research_lab/`, `paper/` ou du VPS modifié.
**Scripts (reproductibles) :** `ichivol-app/engine/scripts/t_exp_review/` (lancer depuis `ichivol-app/engine` avec `PYTHONPATH=.`).

## 1. Verdict en trois lignes

- Le simulateur est **mécaniquement correct** : mon code indépendant, écrit à partir du modèle d'exécution documenté, retombe **à l'euro près** sur la référence (1 371 transactions, brut +971,9, frais 1 394,6, net −1 817,2, 699 longs / 672 shorts, capital final 3 182,8).
- Aucun défaut trouvé ne change le signe du résultat. Les deux plus gros leviers ne sont pas des bugs : **les shorts** (−1 417 € sur −1 817 €) et **le barème de commission** (5 bps au lieu de 7,5–10 bps réels sur le spot).
- PPO / BEST Cloud utilisés comme filtres d'entrée **n'améliorent pas l'espérance par transaction** ; les gains en € viennent uniquement d'un nombre de transactions plus faible.

Limite de mon indépendance : j'ai lu `sim.py` avant d'écrire mon code. La concordance exacte prouve que l'implémentation est fidèle au modèle documenté, pas que les choix de modélisation sont justes ; c'est pourquoi j'ai mesuré chaque choix ci-dessous.

## 2. Ce qui a été vérifié et est correct

| Point | Constat |
|---|---|
| Décision à la clôture de t, fill à l'ouverture de t+1 | Correct ; pas d'usage du prix de la barre de décision comme prix d'exécution. |
| Stop / objectif dans la même barre | Stop d'abord : prudent. Fill à l'ouverture en cas de gap : correct. |
| Alignement 4H (MTF) | `_align_mtf_directions` n'utilise que les barres 4H **entièrement closes à l'ouverture** de la barre 1H : causal (légèrement en retard, jamais en avance). |
| Fraîcheur du cache | Signaux recalculés avec le pipeline **actuel** pour BTC, PEPE, APT (12 904 barres chacun) : **0 divergence** avec `signals_v1.pkl`. |
| Caps de risque | Positions max, risque cumulé 4 %, notionnel 25 %, arrêt journalier : implémentés comme documenté. |

## 3. Défauts et fragilités (mesurés, du plus important au plus faible)

Mesures : mon simulateur, fenêtre 2026-01-01 → 2026-09-20 16:00, frais de base, référence −1 817,2 €.

| # | Sujet | Sévérité | Effet mesuré | Recommandation |
|---|---|---|---|---|
| 1 | **Shorts sur du spot** : Binance spot ne vend pas à découvert ; aucun financement / emprunt dans le barème de base. 672 des 1 371 transactions sont des shorts. | Élevée (interprétation) | Long : −401 € · Short : −1 417 €. **Long seul : −381 €**, brut +1 236 € (697 transactions). | Présenter le découpage long/short en tête de l'étude ; ajouter un coût d'emprunt au barème de base. |
| 2 | **Commission 5 bps** (profil actuel) < frais spot standard 10 bps (7,5 avec BNB). | Élevée | Avec le barème par instrument (§4) : 5 bps −1 605 · 7,5 bps −2 146 · 10 bps −2 601 · 2 bps (maker) −811. | Rejouer aussi à 7,5 / 10 bps comme scénario de référence « réaliste ». |
| 3 | **Un seul tirage** pour l'ordre de priorité aléatoire (seed 7). | Moyenne | 10 seeds : moyenne −1 740, écart-type 45, plage −1 817 … −1 662 ; ordre alphabétique −1 687. Le chiffre de référence est le plus pessimiste des tirages. | Publier moyenne ± écart-type sur ≥ 10 seeds. |
| 4 | **Spread entier** compté par côté (au lieu du demi-spread). | Moyenne (prudent) | Demi-spread : −1 595 (**+222 €**). | Déjà noté dans l'étude ; garder mais le chiffrer. |
| 5 | **Look-ahead mineur** : le plafond de liquidité (2 % du volume) utilise le volume de la barre d'entrée **elle-même**, connu seulement à sa clôture. | Faible (biais réel mais petit) | Version causale (volume de la barre précédente) : −1 844 (**−27 €**), 10 transactions de plus. | Utiliser le volume de la barre précédente ou une médiane glissante. |
| 6 | **Stops remplis exactement au niveau**, sans glissement supplémentaire sur les mèches rapides. | Faible | +10 bps de glissement sur les stops : −1 891 (**−74 €**). L'objectif « avec traversée » ne change rien (0 €). | Glissement de stop proportionnel à l'ATR de la barre. |
| 7 | **Pas de quantification** des prix au tick ni de la quantité au pas ; minimum de notionnel 10 € alors que Binance impose 5 USDT (1 pour PEPE / DOGE). | Faible sur A, plus forte pour PEPE | Non chiffré (nécessite les niveaux de stop arrondis). | Arrondir fills, stops et objectifs au tick, dans le sens défavorable. |
| 8 | **Réconciliation du grand livre tautologique** : le livre est alimenté par les mêmes montants que la trésorerie ; elle détecte une dérive comptable, jamais un biais économique. | Information | — | Ne pas la présenter comme validation du modèle. |
| 9 | Détails : la référence de l'arrêt journalier est l'équité à la **clôture de la 1ʳᵉ barre** du jour (pas la veille) ; un fill refusé (liquidité, notionnel min.) « brûle » la série de signal ; les plafonds ne sont pas re-testés au moment du fill. | Très faible | 12 + 3 refus concernés. | À documenter. |

## 4. Barème de coûts par instrument (proposition)

Source : `exchangeInfo` (tickSize, minNotional) et un instantané `bookTicker` du 2026-09-20 (lecture publique, données `data-api.binance.vision`). **Constat : pour les 19 paires cotées, le spread affiché vaut exactement 1 tick** (TONUSDT : carnet vide / gelé). Le coût d'entrée d'un ordre au marché est donc ≈ **0,5 tick** + glissement.

Friction par côté = 0,5 × (tick / prix) + glissement selon la liquidité (médiane du volume horaire en USDT : ≥ 2 M → 1 bp ; 0,4–2 M → 2 bps ; < 0,4 M → 4 bps). **Le palier de glissement est une hypothèse, non mesurée.**

| Instrument | Tick / prix (bps) | Notionnel min. (USDT) | Friction / côté proposée (bps) | Base actuelle |
|---|---:|---:|---:|---:|
| PEPEUSDT | 25,25 | 1 | **14,6** | 5 |
| APTUSDT | 13,81 | 5 | **10,9** | 5 |
| DOTUSDT | 9,00 | 5 | 8,5 | 5 |
| OPUSDT | 8,06 | 5 | 8,0 | 5 |
| TONUSDT (gelé) | 6,25 | 5 | 7,1 | 5 |
| ATOMUSDT | 5,71 | 5 | 6,9 | 5 |
| ARBUSDT | 4,90 | 5 | 6,5 | 5 |
| ADAUSDT | 4,45 | 5 | 4,2 | 5 |
| NEARUSDT | 2,56 | 5 | 3,3 | 5 |
| LTCUSDT | 1,74 | 5 | 2,9 | 5 |
| SUIUSDT / UNIUSDT | 1,18 / 1,15 | 5 | 2,6 | 5 |
| AVAXUSDT / LINKUSDT | 0,88 / 0,81 | 5 | 2,4 | 5 |
| DOGEUSDT | 1,17 | 1 | 1,6 | 5 |
| SOLUSDT / XRPUSDT | 0,92 / 0,72 | 5 | 1,5 / 1,4 | 5 |
| BNBUSDT / ETHUSDT / BTCUSDT | 0,13 / 0,04 / 0,00 | 5 | 1,0 | 5 |

Effet sur A (commission inchangée à 5 bps) : **−1 605 €** contre −1 817 € : le barème plat **surestime** le coût des majeures plus qu'il ne sous-estime celui de PEPE / APT / DOT / OP (43–69 transactions chacune sur 1 371). Corriger la friction ne rend donc pas A rentable ; c'est la commission qui domine (§3, ligne 2).

À faire pour calibrer pour de vrai : journaliser un instantané `bookTicker` toutes les N minutes pendant plusieurs semaines (distribution du spread, profondeur au meilleur prix) ; ne pas dériver un spread des bougies (l'estimateur de Corwin–Schultz donne 8–40 bps, dominé par la volatilité, inutilisable ici).

## 5. PPO / BEST Cloud comme filtres d'entrée (banc de recherche, hors `paper/`)

Paramètres fixés avant tout résultat : PPO 12/26/9, BEST Cloud EMA 20 / EMA 50 ; les filtres ne font que **retirer** des entrées (sorties, taille, plafonds inchangés). Deux fenêtres disjointes, deux scénarios de coûts. Fenêtres : DEV = 2025-06-01 → 2026-01-01, VAL = 2026-01-01 → 2026-09-20.

| Fenêtre | Filtre | Trans. | Net (€) | Net / trans. | Brut / trans. |
|---|---|---:|---:|---:|---:|
| DEV | A (aucun) | 1 197 | −2 564 | **−2,14** | −0,29 |
| DEV | F1 PPO côté (ppo et histogramme du bon côté) | 1 109 | −2 456 | −2,21 | −0,33 |
| DEV | F2 PPO STRONG (histogramme qui accélère) | 1 060 | −2 341 | −2,21 | −0,28 |
| DEV | F3 BEST Cloud aligné | 1 123 | −2 600 | −2,32 | −0,45 |
| DEV | F4 F1 + F3 | 1 045 | −2 497 | −2,39 | −0,52 |
| VAL | A (aucun) | 1 371 | −1 817 | **−1,33** | +0,71 |
| VAL | F1 | 1 297 | −1 732 | −1,34 | +0,76 |
| VAL | F2 | 1 261 | −1 681 | −1,33 | +0,77 |
| VAL | F3 | 1 301 | −1 680 | −1,29 | +0,79 |
| VAL | F4 | 1 238 | −1 608 | −1,30 | +0,83 |

Coûts défavorables : même conclusion (net / transaction VAL : −2,61 pour A contre −2,68 / −2,71 / −2,66 / −2,72).

**Lecture :**

- L'espérance nette par transaction est **inchangée** (écarts de ±0,05 €, sans signification statistique avec ~1 100–1 400 transactions dont l'écart-type est bien supérieur). Le « gain » en € vient de 5–12 % de transactions en moins, chacune perdante en moyenne.
- Sur DEV, A a **déjà un brut négatif** (−341 €) : aucun filtre ne peut créer d'avantage brut là où il n'y en a pas ; BEST Cloud aligné y **dégrade** le brut par transaction (−0,29 → −0,45 / −0,52), ce qui est compatible avec sa redondance vis-à-vis d'Ichimoku.
- PPO STRONG est neutre (ni utile ni nuisible mesurable). Aucun de ces résultats ne justifie d'entrer dans la confluence (T5).
- Non fait : PPO / BEST Cloud comme **règle de sortie** (le harnais `research_lab` pilote les sorties par décision ; à tester séparément, la rotation étant déjà le problème principal). Non fait : matrice de redondance sur données réelles.

## 6. Recommandations pour l'étude (ichivol-69)

1. Titre de l'étude : présenter **long seul** et **long + short** côte à côte ; le résultat « A perd » est en majorité un résultat « les shorts perdent ».
2. Rejouer A / E avec commission 7,5 et 10 bps en plus de 5 bps, moyenne sur ≥ 10 seeds.
3. Corriger le plafond de liquidité (volume de la barre précédente) — effet faible, mais c'est le seul vrai look-ahead relevé.
4. Adopter le barème par instrument du §4 comme scénario « coûts réalistes », en signalant que le palier de glissement est une hypothèse.
5. Ne pas déduire de la réconciliation du grand livre une validation économique du simulateur.
