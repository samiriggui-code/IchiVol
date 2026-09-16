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

- **Matrice, Table (Décisions/Market/Overview), détail (Bias/sheet)** : **Portes** = badge d’action ; **Brut/combiner** = diagnostic secondaire. → esprit **B** partout dans l’UI.
- **Overview (tuiles Achats/Ventes/Surveillance)** : comptées sur la porte quand elle est dispo (fallback combiner sinon) — plus de double vérité entre le résumé et le détail.
- **Copilot** : explique le verdict fourni ; **ne vote pas** et ne “migre” pas en C. Bouton *Écart portes* pour pointer explicitement un désaccord combiner/portes.
- **Journal** : seul endroit qui garde Combiner et Portes **côte à côte** en colonnes distinctes — normal, c’est un historique d’audit, pas une surface d’action.

Quand un handoff dit « on reste Option A / pas Option C », lis :  
*« on ne kill pas encore le combiner dans le moteur / la DB (Option C toujours pas justifiée par les backtests) ; mais côté UI, plus aucune surface d’action n’affiche le combiner seul sans passer par les portes — Option B est maintenant la règle partout, pas juste sur la Matrice. »*

### Pourquoi ça ne devrait plus dériver

La dérive Table/Overview venait de **4 implémentations locales dupliquées** de la règle « porte prioritaire, combiner en diagnostic » (une par écran, chacune ad hoc). Depuis le fix du 2026-09-16, il n’y a plus qu’une seule source :

- [`src/lib/verdict.ts`](../ichivol-app/src/lib/verdict.ts) — `asGate` / `gateTone` / `decisionTone`
- [`src/components/VerdictBadge.tsx`](../ichivol-app/src/components/VerdictBadge.tsx) — le rendu (porte primaire + combiner en `brut …` secondaire, fallback combiner seul si pas de pipeline)

**Règle pour tout nouvel écran qui affiche un verdict : importer `VerdictBadge`, ne pas réinventer un badge combiner-only.** Si tu vois un badge `STRONG_BUY`/`BUY`/… affiché seul sans passer par ce composant, c’est un retour en arrière vers Option A — pas une nouvelle stratégie.
