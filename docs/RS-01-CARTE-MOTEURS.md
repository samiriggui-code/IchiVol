# RS-01 — Carte des moteurs IchiVol et de leur usage réel

**Chantier :** RS « stratégie alternative » (pilotage Claude local, 2026-09-28).
**Base vérifiée :** `main` @ `3bbd6ed`, lecture du code (`app/decision/pipeline.py`, `app/paper/engine.py`, `app/paper/strategy_profiles.py`, `app/indicators/*`), recoupée avec l'audit VP-P ([`VP-P-PAPER-REEL.md`](./VP-P-PAPER-REEL.md), PR #159).
**Règle de lecture :** c'est le code qui fait foi. Toutes les décisions paper sont prises sur la bougie 1h **close** `t` et exécutées à l'ouverture suivante (≈ `open(t+1)`).

## 1. Réponse courte

- **Une décision BUY paper exige :**
  1. direction Ichimoku LONG ;
  2. régime non bloquant : ATR ni mort ni extrême, ADX en tendance, **cassure Donchian 20** ;
  3. pas de BOS **baissier** ;
  4. RVOL pas « faible » ;
  5. emplacement acceptable : pas de congestion HVN, pas sous la value area, pas sous l'AVWAP.

  Les étapes en « WATCH » **laissent passer**.
- **FVG, Fibonacci, CHOCH, zones S/R, trendlines, liquidité :** **aucun rôle** dans les décisions paper. Le profil `ICHIVOL_BASELINE_V1` a `structure_filter=None`, `fibonacci_filter=None` et le contexte désactivé. Ces objets servent à l'affichage (Chart Intelligence), à « Pourquoi ? » (AW1), au contexte de l'IA et au Strategy Lab.
- **BOS :** sert **uniquement d'invalidation** (un BOS baissier bloque un LONG). Un BOS haussier ne déclenche rien.
- **MTF 4h :** **jamais bloquant**. Il ne fait que passer l'étape structure en WATCH.
- **Sorties :** stop `1.5 × ATR(14)`, objectif `2R` (ancrés sur le prix d'exécution), sortie quand la direction Ichimoku n'est plus LONG. En pratique, 94 % des sorties sont stop ou objectif (VP-P §3.1).
- **Taille :** 0,5 % de risque visé, mais plafond de 10 % par position **toujours atteint** en crypto, soit un risque réel d'environ 0,2 % (VP-P).

## 2. Table de correspondance

Rôles :
- **A** = affichage graphique ;
- **IA** = contexte agent / AW1 ;
- **F** = filtre bloquant ;
- **W** = modulation non bloquante (WATCH) ;
- **D** = déclencheur d'entrée ;
- **I** = invalidation ;
- **S** = sortie ;
- **T** = dimensionnement ;
- **L** = Strategy Lab / recherche seulement.

| Objet | Calcul | Disponible à (barre `i`) | Usage paper réel | Autres usages | Rôle possible dans une stratégie |
|-------|--------|--------------------------|------------------|---------------|-----------------------------------|
| Ichimoku (TK, nuage, chikou, direction) | `indicators/ichimoku.py`, `agents/ichimoku_agent` | close `i` ; nuage **affiché** = données ≤ `i−26` | **D** (direction LONG) + **S** (sortie direction) | A, IA, VP3 B1–B7 | Filtre de régime lent, sortie de tendance |
| RVOL | `indicators/rvol.py` | close `i` (fenêtre 20, percentile 100) | **F** si `LOW` ; W sinon | A, IA | Filtre de participation |
| CVD | `indicators/cvd.py` | close `i` | Texte seulement (étape participation) | A, IA | Confirmation de pression acheteuse (non testé) |
| OI / funding | `indicators/oi_funding.py` | close `i` (perp) | Texte seulement | IA | Filtre de foule (non testé) |
| ATR(14) + régime | `indicators/atr.py` | close `i` | **F** (DEAD < p15, EXTREME > p90) + **T** (stop 1.5 ATR) + **S** (stop) | A | Stop, trailing, sizing |
| ADX(14) | `indicators/adx.py` | close `i` | **F** (TRENDING / STRONG requis si lecture confirmée) | IA | Filtre de tendance |
| Donchian 20 | `indicators/donchian.py` | close `i`, bandes = **barres `i−20..i−1`** (barre signal exclue) | **F** (cassure UP requise dans le régime) | A | **Déclencheur de cassure** (période paramétrable : 55/20 possible sans nouveau code) |
| Structure : swings, biais, BOS | `indicators/structure.py` + `pivots.fractal_confirmed_at` | swing `j` connu à `j + 2` ; BOS « confirmed » à sa confirmation | **I** (BOS baissier) ; biais opposé → W | A, IA, AW1 | Déclencheur BOS confirmé, invalidation structurelle |
| CHOCH | `indicators/structure.py` (T9b) | à confirmation | **Aucun** | A, AW1, L (`strategy_lab/conditions.py`) | Invalidation / changement de régime |
| Location (VP, VAH/VAL, POC, VWAP, AVWAP) | `indicators/location.py` | close `i` (lookback 100) | **F** (HVN, sous VAL, sous AVWAP) | A, IA | Filtre d'emplacement |
| FVG | `indicators/fvg.py` | **close de la 3ᵉ bougie** ; remplissage / invalidation mis à jour causalement | **Aucun** | A, AW1, L | Zone de retour (pullback) |
| Impulsion + Fibonacci | `indicators/impulse.py`, `fibonacci/context.py` | impulsion connue à la confirmation du pivot final | **Aucun** (porte Fib désactivée dans le baseline) | A, AW1, L, profil expérimental F | Zone de retour à ancrage causal |
| Zones S/R, trendlines | `app/structure/*` (consensus détecteurs) | selon le détecteur | **Aucun** (`structure_filter=None`) | A, AW1 | Niveaux d'invalidation |
| Liquidity / Confluence | job CI-LIQ-CONF (en cours) | à définir (pivots confirmés) | **Aucun** (observe-only) | A | Zones déduites des prix (ce ne sont **pas** des ordres observés) |
| Cycle (T-CYCLE) | `app/cycle/` | close `i` | **Aucun** (observe-only, gel) | IA | Filtre de régime temporel (non testé) |

## 3. Délais de disponibilité (règle pour tout backtest RS)

Pour tout objet, on distingue trois dates :
- `t_graph` = date affichée sur le graphique (le pivot, la 1ʳᵉ bougie du FVG…) ;
- `t_known` = première barre close où il est calculable :
  - swing : `t_graph + 2` barres ;
  - FVG : close de la 3ᵉ bougie ;
  - BOS confirmé : barre de confirmation ;
- `t_decide` = barre close à laquelle une règle peut l'utiliser, **≥ `t_known`**. L'exécution a lieu à `open(t_decide + 1)`.

Les champs décrivant un événement **ultérieur** (FVG `filled`, niveau `swept`, BOS `broken`…) ne peuvent être lus qu'à la barre où ils se produisent, **jamais** projetés en arrière. C'est déjà le cas dans le moteur (tests de troncature `tests/indicators/test_*_lookahead.py`) et dans le replay walk-forward de Chart Intelligence (CI-R1).

## 4. Ce que ça implique pour la recherche

1. **Une bibliothèque d'objets n'est pas une stratégie.** Aujourd'hui, la décision paper n'exploite ni FVG, ni Fib, ni CHOCH, ni les zones. Le résultat négatif de B7 / VP-P ne dit **rien** sur ces objets.
2. **B7 contient déjà une cassure Donchian 20.** Un candidat « Donchian 55 / sortie de tendance » ne se distingue donc pas de B7 par l'idée de cassure. Il s'en distingue par :
   - l'**absence** des autres filtres ;
   - l'**unité de temps** (4h au lieu de 1h) ;
   - surtout la **sortie** : pas d'objectif 2R, trailing large.

   C'est précisément la dimension que VP3 et VP-P n'ont pas testée : les sorties de B7 coupent la queue droite, un objectif 2R dans le bruit horaire.
3. **Composants réutilisables sans nouveau calcul de marché :** Donchian (période paramétrable), ATR, structure / BOS confirmé, FVG, impulsion / Fib, simulateur `research_lab/sim.py` (capital commun, coûts par symbole, options VP-P).
