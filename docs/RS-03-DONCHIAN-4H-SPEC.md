# RS-03 — Candidat RS-D1 « Cassure Donchian 4h + sortie de tendance » : règles et critères figés

**Statut :** **pré-enregistré avant tout code et tout run** · amendement `VP0-2026-09-28b` (Question RS-D) · pilote Claude local · 2026-09-28.
**Hypothèse économique :** en crypto spot, quelques tendances prolongées peuvent compenser les fausses cassures et les coûts **si l'on ne coupe pas la queue droite**. Pas d'objectif fixe, un stop suiveur large et une sortie de canal.
**Ce que RS-D1 n'est pas :**
- **ni** une correction de B7 ;
- **ni** une reproduction de Turtle / NFI ;
- **ni** une stratégie validée.

C'est **une** hypothèse, sans recherche de paramètres. Les valeurs 55 / 20 / 14 / 3 sont la proposition de référence de Samir. Elles ne viennent d'**aucune** optimisation sur IchiVol.

**Pourquoi ce premier candidat (et pas la famille structurelle RS-04) :**
- il réutilise des composants existants et déjà testés contre le lookahead (`indicators/donchian.py`, `indicators/atr.py`, `research_lab/sim.py` avec les options paper de #159) ;
- il comporte peu de règles, donc peu de choix subjectifs ;
- il est lent (4h) et prend peu de trades, donc les **coûts** pèsent peu ;
- il vise précisément la dimension que VP3 et VP-P n'ont pas testée : les **sorties qui laissent courir**.

---

## 1. Données et fenêtres

| Élément | Valeur figée |
|---------|--------------|
| Actifs | BTCUSDT, ETHUSDT, SOLUSDT **spot**, long seulement |
| Série | VP1 figée 4h (Binance Vision, sha256 du manifeste), **tronquée au chargement** à `open_time < 2025-01-01T00:00Z`. **Test obligatoire** : aucune barre ≥ 2025 n'atteint la stratégie |
| Warm-up | 2020-09-01 → 2021-06-30 (indicateurs seulement, aucune position) |
| Fenêtre de score | **parcours continu** 2021-07-01 → 2024-12-31 (union des plis WF1–WF7) |
| Interdit | Validation 2025, holdout 2026, tout dataset externe, toute variante de paramètre |
| Trous de données | Aucune décision sur une barre absente. Les fenêtres 55 / 20 / 14 se comptent **en barres disponibles**. Si une barre manque pendant une position, les protections s'appliquent à la barre disponible suivante (règle de gap) |

## 2. Indicateurs (tous connus à la clôture de la barre `t`)

- `U55[t] = max(high[t−55 .. t−1])` : Donchian haut, **barre `t` exclue** (`indicators/donchian.py`, `period=55`).
- `L20[t] = min(low[t−20 .. t−1])` : Donchian bas, barre `t` exclue (`period=20`).
- `ATR[t]` = moyenne **simple** du true range sur 14 barres. C'est la définition du moteur (`indicators/atr.py`), **pas** Wilder.

## 3. Entrée

- **Signal** à la clôture de `t` si :
  - `close[t] > U55[t]` ;
  - aucune position ouverte sur l'actif ;
  - aucun ordre d'entrée déjà en attente sur l'actif.
- **Exécution** à `open(t+1)` : prix d'exécution `fill = open(t+1) × (1 + friction)`, commission en plus (coûts §6).
- **Réentrée** : autorisée dès qu'un signal apparaît à une clôture **strictement postérieure** à la barre de sortie. Il n'y a pas de notion de « série » : la condition est un état. Si la condition est déjà vraie à la clôture de la barre de sortie, la réentrée se fait au plus tôt sur le signal de la barre suivante.
- **Aucun autre filtre** : pas d'Ichimoku, de RVOL, d'ADX, de régime ATR, de structure ni de MTF. Rien de B7 n'est hérité.

## 4. Protection et sorties

- **Stop initial** : `S₀ = fill − 3 × ATR[t]` (ATR de la barre signal, ancré sur le **prix d'exécution**, comme le paper).
- **Stop suiveur** : à la clôture de chaque barre `k ≥` barre d'entrée :
  - `candidat[k] = max(close[entrée .. k]) − 3 × ATR[k]` ;
  - `S[k+1] = max(S[k], candidat[k])`.

  Le stop ne fait que **monter**. Il ne s'applique qu'**à partir de la barre `k+1`**.
- **Sortie de canal** : si `close[k] < L20[k]`, sortie à `open(k+1)`.
- **Exécution du stop pendant la barre `j`** (y compris la barre d'entrée, à partir de l'open) :
  - `open[j] ≤ S[j]` → sortie à `open[j]` (gap) ;
  - sinon `low[j] ≤ S[j]` → sortie à `S[j]`.
- **Priorité** : dans une barre `j`, le stop intrabarre est contrôlé en premier. Une sortie de canal décidée à la clôture `k` est exécutée à `open(k+1)`. Si ce même `open(k+1)` est sous `S[k+1]`, le motif est `stop_gap`, au même prix.
- Pas d'objectif fixe (pas de 2R), pas de time-stop, pas de renforcement, pas de levier, une position par actif.
- **Fin de fenêtre (2024-12-31)** : les positions restantes sont **valorisées au dernier close** dans l'equity, sans vente forcée. Pour les statistiques de trades, elles sont comptées à part (`open_at_end`, P&L latent).

## 5. Taille et capital (contraintes du paper conservées)

| Élément | Valeur |
|---------|--------|
| Capital | **5 000**, commun aux 3 actifs, parcours continu |
| Taille | `qty = 0,5 % × equity_coût / (fill − S₀)`, plafonnée à **10 %** d'`equity_coût`. Ordre limité au cash, refusé s'il tombe sous **25 %** de la taille visée ; minimum **10** |
| `equity_coût` | cash + notionnels ouverts au coût (définition paper, option `gate_equity="cost"` de #159) |
| Limites | risque ouvert initial cumulé ≤ **4 %** ; perte journalière **3 %** → aucune nouvelle entrée jusqu'au jour UTC suivant ; ordre de traitement aléatoire seed **7** si plusieurs signaux arrivent en même temps |
| Arrondis | quantités fractionnaires (pas de lot), prix non arrondis, fidèle au simulateur |

Attendu (information, pas un critère) : `3 ATR` en 4h ≈ 5–8 % du prix, donc un notionnel ≈ 6–10 % du capital par position. Exposition maximale ≈ 30 % avec 3 actifs. **La comparaison doit donc se faire à exposition comparable** (référence B0-E, §7).

## 6. Coûts

- **Paper (base)** : commission **7,5 bps** par côté + friction par symbole du profil (BTC **1,0**, ETH **1,0**, SOL **1,5** bps par côté), slippage 0.
- **Adverse (stress)** : commission **10** + spread `max(friction, 4)` + slippage **8** bps par côté.

## 7. Références comparées (mêmes actifs, dates, capital, coûts)

| Réf. | Définition | Question à laquelle elle répond |
|------|-----------|--------------------------------|
| **B7-P** | B7 paper fidèle sur BTC / ETH / SOL 1h, capital commun 5 000 : run **R4 de #159** (P2), **après** ses corrections v2 | RS-D1 fait-il mieux que la stratégie actuelle sur le même périmètre ? |
| **B0-F** | Buy & hold **pleinement investi** : 1/3 du capital par actif acheté à l'open du 2021-07-01 (coûts d'entrée paper), jamais revendu, valorisé au close | Que rapporte la détention passive totale (et quelle chute) ? |
| **B0-E** | Allocation passive **réduite** : panier équipondéré des 3 actifs à un poids constant `e` du capital, reste en cash, rééquilibré le 1ᵉʳ de chaque mois (coûts paper). `e` = **exposition moyenne réalisée de RS-D1** sur la fenêtre, calculée mécaniquement (aucun choix de performance) | Le **timing** de RS-D1 apporte-t-il quelque chose par rapport à la même exposition moyenne tenue passivement ? |
| Cash | 0 % | Repère |

B0-F et B0-E n'ont **pas** de stop. On ne leur applique aucune règle de « risque 0,5 % au stop ».

## 8. Critères de jugement (figés avant le run)

Mesures sur le parcours continu, coûts **paper** sauf mention. Intervalles : **bootstrap par mois calendaire** (on tire des mois entiers, tous actifs confondus), 10 000 tirages, seed 7, intervalle percentile à 95 %.

| # | Critère « candidat à validation supplémentaire » (tous requis) |
|---|---------------------------------------------------------------|
| **D1** | Rendement net > 0 **et** borne basse (95 %) de la moyenne des rendements **mensuels** > 0 |
| **D2** | Max drawdown (equity par barre) **≤ 15 %** |
| **D3** | Borne basse (95 %) de la moyenne de `Δ` mensuel **(RS-D1 − B7-P)** > 0 |
| **D4** | Calmar (CAGR / \|maxDD\|) de RS-D1 **>** Calmar de **B0-E** |
| **D5** | Rendement net > 0 sur **≥ 2 des 3** actifs (contribution par actif dans le portefeuille commun) **et** sur **≥ 4 des 7** plis (découpage du parcours continu) |
| **D6** | Rendement net > 0 aussi en coûts **adverses** |
| **D7** | **≥ 30** trades clôturés sur la fenêtre (sinon NON CONCLUANT) |

**Verdict :**
- **CANDIDAT À VALIDATION SUPPLÉMENTAIRE** : D1 à D7 vrais. Aucune validation 2025 ni aucun holdout n'est ouvert automatiquement : la suite est une décision de Samir.
- **REJETÉ** : rendement net ≤ 0 en base, **ou** maxDD > 15 %.
- **NON CONCLUANT** : tous les autres cas, par exemple rendement positif mais intervalle qui inclut 0, ou moins de 30 trades. Le rapport dit alors ce que les données **excluent** et **n'excluent pas**.

Une stratégie qui perd moins que B7 mais détruit du capital est **REJETÉE** (D1).

## 9. À reporter (obligatoire, descriptif)

- Capital final, rendement net, CAGR.
- Max drawdown, **temps de récupération**.
- Trades : nombre et durée (médiane, moyenne).
- Exposition moyenne et maximale, temps en position.
- Réussite, gain et perte moyens, espérance (€, R, % du notionnel), profit factor.
- **Poids des frais** (€ et % du brut).
- Ventilation par actif, par pli et par année.
- **Concentration** : part du P&L des 1, 3 et 5 meilleurs trades ; P&L sans les 3 meilleurs. C'est **descriptif et non bloquant** : une stratégie de tendance dépend par construction de ses meilleurs trades.
- Motifs de sortie : stop initial, stop suiveur, canal, gap.
- Sensibilité à l'exécution : **décalage d'une barre** de l'exécution (open `t+2`) en analyse de stress, **non bloquante**.
- Journal complet des trades (JSON).

## 10. Contrôles d'implémentation exigés avant le run

1. **Troncature stratégie** (à la Freqtrade `lookahead-analysis`) : les signaux, les niveaux `S[k]` et les ordres jusqu'à `t` doivent être identiques, que la série s'arrête à `t` ou continue.
2. Tests unitaires :
   - stop monotone ;
   - mise à jour appliquée seulement à `k+1` ;
   - gap sous le stop → exécution à l'open ;
   - sortie de canal à `open(k+1)` ;
   - réentrée pas avant la clôture suivant la sortie ;
   - taille et plafond 10 % ;
   - refus sous 25 % ;
   - coûts par symbole.
3. Troncature ≤ 2024 vérifiée par une assertion.
4. B0-F et B0-E : tests de valorisation et de rééquilibrage.
5. Implémentation **isolée** (`ichivol-app/engine/rs/`), réutilisant `research_lab/sim.py` et les options de #159. **Aucun** changement du paper, du pipeline ni des défauts du simulateur.

## 11. T10b

+1 ligne `RS-D1-U3-4h` (hypothèse de stratégie). Pas de DSR : jugement par D1–D7, avec intervalles bootstrap. Toute variante (55/20/14/3 modifiés, autres actifs, 1h, filtre ajouté) = **nouvelle** ligne et nouvel amendement, **avant** le run.
