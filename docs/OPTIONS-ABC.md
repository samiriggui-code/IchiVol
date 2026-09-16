# Options A / B / C — le glossaire qui revient tout le temps

**Une phrase :** ce n’est **pas** trois stratégies de trading. C’est **trois façons d’afficher / croire** le verdict du moteur, parce qu’il y a encore **deux calculateurs** en parallèle.

---

## Les deux calculateurs (le fond du problème)

| Nom | Ce qu’il regarde | Sortie |
|-----|------------------|--------|
| **Combiner legacy** | Ichimoku × RVOL seulement (Direction + Participation) | `STRONG_BUY` … `STRONG_SELL` (6 badges) |
| **Pipeline à portes** | Direction → Participation → Structure/MTF → Location → Régime | `BUY` \| `SELL` \| `WATCH` \| `NO_TRADE` |

Ils peuvent **se contredire** (ex. NEARUSDT : badge ACHAT, portes PAS DE TRADE).  
Ce n’est pas deux “edges” : le combiner est un **sous-ensemble** du pipeline.

---

## Les trois options (décision produit / UI)

| Option | En français | État |
|--------|-------------|------|
| **A** | On **garde les deux visibles** : table/badge = combiner ; détail/sheet = portes | Point de départ historique |
| **B** | Pour **agir** (humain, paper, agent), on ne suit plus que les **portes** ; le badge combiner devient **diagnostic** (secondaire) | **Déjà tranché** côté Matrice (colonne Portes = action, Brut = legacy) |
| **C** | On **supprime** le combiner comme vérité produit : plus que le pipeline partout (DB, backtest, badges) | **Pas fait** — et **pas justifié** tant que les backtests ne le soutiennent pas |

---

## Pourquoi on répète « Option C non justifiée »

On a backtesté la variante `PIPELINE` vs `ICHIMOKU_ONLY` (plusieurs fenêtres, puis sweep élargi).

- **Sharpe / rendement** : le pipeline **ne bat pas** Ichimoku seul assez souvent → pas d’edge de yield prouvé.
- **Drawdown** : le pipeline **réduit le risque** presque partout → utile comme **filtre de risque**, pas encore comme **remplaçant unique** du verdict.

Donc : **ne pas migrer toute la vérité produit sur les portes seules (Option C)** tant qu’on n’a pas une preuve d’edge.  
On peut déjà **agir sur les portes (Option B UI)** sans jeter le combiner des stats / legacy.

---

## Ce que tu vois dans l’app aujourd’hui

- **Matrice** : **Portes** = verdict d’action ; **Brut** = combiner (diagnostic). → esprit **B** pour l’UI.
- **Table / certains badges** : encore un peu l’esprit **A** (legacy présent).
- **Copilot** : explique le verdict fourni ; **ne vote pas** et ne “migre” pas en C.

Quand un handoff dit « on reste Option A / pas Option C », lis :  
*« on ne kill pas encore le combiner dans le moteur / la DB ; les portes ne sont pas encore la seule vérité technique partout — même si l’UI Matrice privilégie déjà les portes pour agir. »*
