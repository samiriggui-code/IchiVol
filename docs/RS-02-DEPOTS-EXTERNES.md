# RS-02 — Références externes : sélection argumentée

**Méthode :**
- clones superficiels hors du dépôt IchiVol, commit épinglé ;
- lecture du code et des documents livrés ;
- **aucun run**, aucune donnée externe importée ;
- les chiffres cités sont **ceux des auteurs, non reproduits**.

Un grand nombre d'étoiles n'est pas pris comme preuve de qualité.

| Dépôt | Commit épinglé | Date | Licence |
|-------|----------------|------|---------|
| iterativv/NostalgiaForInfinity | `fc3c7cee28ad6459bc25fd5ce551678654868211` | 2026-09-27 | GPL-3.0 |
| pst-group/pysystemtrade | `52a4f0e7a0966f57a1498ead4c23b9713c22add6` | 2026-09-26 | GPL-3.0 |
| joshyattridge/smart-money-concepts | `1b62fd6c41e1f508e7ed76831a039fa4c82d42f6` | 2026-04-03 | MIT |
| freqtrade/freqtrade | `d6c736fc1797b453b88e6370a556d6a7cafa0220` | 2026-09-27 | GPL-3.0 |
| freqtrade/freqtrade-strategies | `f3340ce11f5bdf62f598522e64d1f5638eaa13f5` | 2026-09-08 | GPL-3.0 |
| aurelien-gentile/turtle-strategy-backtest | `4a975e6d20a7e6190f350b6443b64631fffcd739` | 2026-07-09 | **aucune licence** (tous droits réservés) |

**Réutilisation :** on **n'importe ni ne copie de code GPL** dans IchiVol (licence du projet non GPL) ni de code sans licence. On s'inspire des **idées et méthodes**, ré-implémentées avec nos propres composants. MIT (smc) serait réutilisable avec mention, mais c'est inutile : voir C.

---

## A. NostalgiaForInfinity (NFI) — **écarté comme candidat ; utile comme contre-modèle**

- **Cadre :** Freqtrade, **5m** obligatoire, `info_timeframes = 15m, 1h, 4h, 1d`, 40 à 80 paires recommandées, 6 à 12 trades ouverts, `startup_candle_count = 800`. Huit fichiers (X à X8), jusqu'à **~80 000 lignes** (X7), **52** conditions d'entrée long distinctes.
- **Gestion des pertes :**
  - `stoploss = -0.99` : **aucun vrai stop** ;
  - `position_adjustment_enable = True` : **renforcements en perte** (« grinding ») à −12 / −16 / −20 %, par paliers de 20–28 % de la mise initiale ;
  - dérisquage autour de −24 % (spot) ;
  - un « bad trade controller » **désactivé par défaut**.

  C'est l'opposé de « pertes maîtrisées » au sens de Samir.
- **Performances documentées :** `docs/backtest-results/binance-spot` = tranches **mensuelles** de 2024, 289 trades, **réussite 96,95 %**, drawdown moyen 1,12 %.
  - Des tranches d'un mois ne disent rien des positions encore en perte à la fin du mois, et un taux de réussite de 97 % est typique d'une gestion qui **porte les perdants**.
  - **Non reproduit.**
- **Risque de contamination 2025–2026 :** le fichier de stratégie a été modifié le **2026-09-27** et les mises à jour sont quasi quotidiennes. On ne sait pas sur quelles périodes les réglages ont été faits. Le risque est **réel mais non établi** : un commit récent soulève la question, il ne prouve pas quelles données ont servi.
- **Adaptation à IchiVol :** pas pertinente. 5m, univers large, renforcements, pas de stop : tout va contre le cadre choisi. La tester sur 3 actifs en 4h ne prouverait rien, ni dans un sens ni dans l'autre.

## B. pysystemtrade — **référence de méthode retenue** (pas de code importé)

- **Règles de tendance présentes :** `ewmac` (croisement de moyennes exponentielles, **normalisé par la volatilité**) et `breakout` (position du prix dans son canal max/min, lissée), plus des règles `carry`, `accel`, `rel_mom`, `mr_wings`.
- **Séparation nette des étapes** (`systems/`) :
  1. `rawdata` ;
  2. `forecasting` : prévision **continue**, pas un signal binaire ;
  3. `forecast_scale_cap` : moyenne absolue 10, plafond 20 ;
  4. `forecast_combine` : poids et multiplicateur de diversification ;
  5. `positionsizing` : **ciblage de volatilité** ;
  6. `portfolio` : poids par instrument et IDM ;
  7. `buffering` : zone morte qui évite de trader les petits écarts, donc les **coûts** ;
  8. `accounts` : P&L, coûts exprimés en unités de Sharpe.
- **Apport pour IchiVol :**
  - (1) l'exposition doit être une **décision explicite** (ciblage de volatilité), pas un sous-produit d'un plafond de 10 % toujours atteint ;
  - (2) les **coûts** se contrôlent par un tampon et par des règles lentes ;
  - (3) une prévision continue évite le « tout ou rien ».
- **À ne pas transposer :** levier, contrats futures, rolls, short, performances publiées (futures multi-classes).

## C. smart-money-concepts (smc) — **comparaison de définitions ; ne pas utiliser en backtest**

Trois **fuites d'information future** dans le code, que nos indicateurs n'ont pas :

| Fonction smc | Problème | Notre équivalent |
|--------------|----------|------------------|
| `swing_highs_lows` | Fenêtre **centrée** (`shift(-(swing_length // 2))`) : le pivot est marqué **à sa date** avec des bougies futures ; défaut 50 bougies | `pivots.fractal_confirmed_at` : pivot connu à `j + 2` seulement |
| `bos_choch` | L'événement est inscrit à l'index d'un **swing antérieur** (`last_positions[-2]`) à partir d'un swing **postérieur**. Les BOS **jamais cassés ensuite sont supprimés**, ce qui revient à lire le futur | `indicators/structure.py` : cassure connue à sa confirmation, rien n'est supprimé rétroactivement |
| `fvg` | Marqué sur la **bougie du milieu** (`shift(-1)`), alors qu'il n'est connaissable qu'à la clôture de la 3ᵉ | `indicators/fvg.py` : connu à la 3ᵉ bougie |
| `liquidity` | Tolérance = `(high.max() − low.min()) × 1 %` sur **toute la série** : lookahead global | CI-LIQ-CONF : tolérance `0.1 × ATR` à la date |
| `ob`, `BrokenIndex`, `MitigatedIndex`, `Swept` | Champs d'événements **ultérieurs** : utiles pour dessiner a posteriori, **interdits** en décision | Idem chez nous : lus seulement à leur barre |

- **Ce que nous calculons déjà correctement :** swings confirmés, BOS / CHOCH causaux, FVG causal, impulsion / Fib à ancrage causal.
- **Ce qui nous manque :**
  - les **order blocks** : dernière bougie opposée avant une impulsion, à rendre causal ;
  - les **retracements** ;
  - le « previous high/low » par session.

  Aucun n'est nécessaire pour le premier candidat.
- **Pour une stratégie :** smc sert de **dictionnaire de concepts**, pas de moteur. Une configuration structurelle doit être bâtie sur **nos** indicateurs causaux (voir RS-04).

## D. Freqtrade + freqtrade-strategies — **méthode de contrôle retenue**

- `lookahead-analysis` : rejoue les backtests sur des données **tronquées** et signale tout indicateur ou toute entrée qui change quand le futur disparaît. `recursive-analysis` : vérifie la stabilité des indicateurs récursifs selon la longueur d'historique (warm-up).
- **Nos équivalents existent déjà :** tests `tests/indicators/test_*_lookahead.py` (troncature) et replay walk-forward de Chart Intelligence. **Exigence reprise pour RS :** un test de troncature **au niveau de la stratégie**. Les décisions et niveaux de stop à la barre `t` doivent être identiques, que la série s'arrête à `t` ou continue après.
- **Limite rappelée :** un contrôle de lookahead réussi **ne prouve pas** la rentabilité et **ne remplace pas** l'audit d'exécution.
- `freqtrade-strategies` : stratégies d'exemple, sans validation hors échantillon. Le dossier `lookahead_bias/` contient des **contre-exemples volontaires**, utiles pédagogiquement. Aucune stratégie retenue.

## E. Turtle crypto (aurelien-gentile) — **contre-exemple instructif, pas une preuve**

Ce que le dépôt affirme : sur BTC horaire, aucune des 343 combinaisons ne bat le HODL entre mi-2023 et début 2024, et un test t « significatif » le confirme sur des fenêtres glissantes.

Limites relevées dans le notebook :
1. **Une seule phase de marché** (haussière), des données qui s'arrêtent en mars 2024, un seul actif pour l'étude de robustesse.
2. **Exposition faible par construction** : 1 % de risque par unité. Comme pour VP3, battre le HODL en rendement brut dans un marché haussier avec une faible exposition est structurellement improbable. Ce n'est pas une information sur le signal.
3. **Test statistique invalide :**
   - 48 fenêtres d'un an qui démarrent **chaque semaine** de 2023, donc qui se recouvrent presque totalement et ne sont pas indépendantes ;
   - `ttest_ind` compare deux **grandeurs différentes** (ratio « stratégie / BTC » contre rendement brut de BTC) comme deux échantillons indépendants ;
   - en plus, les fenêtres qui commencent après mars 2023 sont **tronquées** par la fin des données.

   La « significativité » ne vaut rien.
4. Entrée sur `High > max(High[−N..−1])`, c'est-à-dire en cours de bougie : il faut un prix d'exécution explicite pour éviter un biais favorable.

**Leçon pour RS :**
- juger une stratégie de tendance sur **plusieurs phases de marché**, avec son **exposition** explicitée ;
- la comparer à une **référence passive d'exposition équivalente**, pas seulement au HODL à 100 % ;
- utiliser des intervalles par **bootstrap en blocs**, jamais un test t sur des fenêtres qui se recouvrent.

---

## Sélection retenue pour la suite

| Rôle | Référence |
|------|-----------|
| Méthode d'allocation / coûts | pysystemtrade (idées : ciblage de volatilité, tampon, prévision continue) |
| Contrôle de lookahead | Freqtrade `lookahead-analysis` (idée) → test de troncature stratégie chez nous |
| Dictionnaire SMC | smc (concepts), **nos** implémentations causales |
| Contre-exemples | NFI (pas de stop + renforcements), Turtle crypto (exposition faible, statistiques invalides) |

**Aucune** de ces références ne fournit une stratégie reproductible qu'on puisse adopter telle quelle. Le premier candidat reste une règle **simple, entièrement spécifiée et testable avec nos composants** : RS-03, Donchian 4h.
