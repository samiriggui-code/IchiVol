# Spécification — profils `FWD_E_LONG` et `FWD_A_LONG` (longs seulement, sortie par direction)

**Auteur :** ichivol-36 · **Date :** 2026-09-20 · **Destinataire :** ichivol-49 (propriétaire de `paper/broker.py`, `paper/engine.py`, profils). **Spécification écrite : aucun code dans `paper/`, `research_lab/`, `screener/`.** Contexte : `PLAN-SUIVI-EN-AVANT-2026-09-20.md`.

## 1. Règles exactes

Notation : `d` = décision du pipeline sur la **dernière bougie clôturée** (BUY / SELL / WATCH / NO_TRADE) ; `dir` = direction Ichimoku de cette même bougie (`pipeline.direction` : LONG / SHORT / NEUTRAL).

### Entrée (identique à A, sauf l'interdit des shorts)
1. Ouvrir un long seulement si `d == BUY`, sans position ouverte sur le symbole, sous les plafonds existants (`max_open_positions`, `max_notional_pct`, `max_open_risk_pct`, `max_symbol_notional_pct`, `daily_loss_limit_pct`) et avec `one_entry_per_signal_run`.
2. Si `d == SELL` : **aucune entrée**. Le rejet est compté sous `short_not_allowed` (seulement si `log_rejections`), et il **ne consomme pas** la série de signal (`signal_already_processed` n'est pas alimenté).
3. Taille, stop (`entry − stop_distance`), objectif (2R), frais et friction : ceux du profil de base, rien de nouveau.

### Sortie — le point qui distingue E de A
| Profil | Un long ouvert est fermé quand… | Raison journalisée |
|---|---|---|
| `FWD_A_LONG` (sortie de A) | `d != BUY` sur une bougie clôturée (WATCH, NO_TRADE **ou** SELL), ou stop, ou objectif | `pipeline_downgraded` / `pipeline_flipped` / `stop_hit` / `take_profit_hit` |
| `FWD_E_LONG` | **`dir != LONG`** sur une bougie clôturée (NEUTRAL **ou** SHORT), ou stop, ou objectif | `direction_flipped` / `stop_hit` / `take_profit_hit` |

Conséquence voulue : sous E, une décision qui retombe à WATCH parce que le RVOL, le régime ou la localisation cessent de valider **ne ferme pas** la position tant que la direction Ichimoku reste LONG. Un long ne se ferme jamais sur un simple changement de la décision.

Pas de vente à découvert à l'ouverture, ni jamais : le nombre de positions `SHORT` sur ces deux portefeuilles doit rester **0**.

### Priorités et cas limites
- **Stop / objectif d'abord** : contrôlés à chaque cycle, avant la règle de direction ; si le stop et l'objectif sont tous deux dans la barre, le stop est supposé d'abord (comportement actuel, à conserver). Un gap au-delà d'un niveau se remplit à l'ouverture / au prix constaté, pas au niveau.
- **Bougies clôturées uniquement** : `dir` est celui de la dernière bougie **clôturée** (`DECIDE_ON_CLOSED_CANDLES=true`, déjà en production). Un changement de direction visible seulement sur la bougie en formation **ne ferme rien**.
- **Données périmées** : si le garde de péremption refuse le symbole (`stale_data`), aucune décision de sortie par direction n'est prise ; les stops et objectifs restent surveillés (moniteur de protection).
- **Une seule fermeture** : rejouer un même cycle ne ferme pas deux fois (garde `status == OPEN` + clé de grand livre — voir `REVUE-D2-LEDGER-…`, points H2/H3).

### Écart connu entre la recherche et le paper live (à documenter, pas à corriger)
Le banc de recherche exécute à l'**ouverture de la barre suivante** ; le paper live exécute au **prix du cycle** qui suit la clôture, avec la friction du profil (retard ≤ une période de synchronisation au lieu d'une barre). Les chiffres de la recherche sont donc une référence d'ordre de grandeur, pas une valeur exacte attendue.

## 2. Champs de profil proposés (sans code)
`exit_mode` : `"decision"` (défaut, comportement actuel) ou `"direction"` ; `allow_short` : `true` (défaut) ou `false`. Valeurs par défaut = comportement actuel, donc `ICHIVOL_BASELINE_V1` et les 11 autres portefeuilles restent identiques. Codes : `FWD_A_LONG` (`decision`, `allow_short=false`), `FWD_E_LONG` (`direction`, `allow_short=false`). Le profil est **figé** pendant les ≥ 8 semaines du plan (pas de nouvelle clé modifiable en cours de test). Les coûts (commission 7,5 bps, barème par instrument) sont ceux du plan de suivi.

## 3. Tests attendus (unitaires, base SQLite jetable, prix fournis à la main)

| # | Scénario | Résultat attendu |
|---|---|---|
| T1 | Long ouvert ; décisions successives BUY, WATCH, WATCH, `dir` = LONG | `FWD_E_LONG` : position **toujours ouverte** ; `FWD_A_LONG` : fermée au premier WATCH (`pipeline_downgraded`) |
| T2 | Long ouvert ; `dir` passe à NEUTRAL | `FWD_E_LONG` fermée, raison `direction_flipped`, prix = prix du cycle − friction de sortie ; aucune nouvelle position |
| T3 | Long ouvert ; `dir` passe à SHORT, `d` = SELL | Fermé (`direction_flipped`) ; **aucun** short ouvert ; compteur `short_not_allowed` +1 si `log_rejections` |
| T4 | Aucune position ; `d` = SELL | Aucun ordre ; `short_not_allowed` +1 ; série de signal non consommée : un BUY plus tard dans la même série reste ouvrable |
| T5 | Long ouvert, stop touché la même bougie où `dir` change | Sortie `stop_hit` (priorité au stop), pas `direction_flipped` |
| T6 | Stop et objectif tous deux dans la barre | `stop_hit` (stop d'abord) ; gap sous le stop : fill au prix constaté, pas au niveau du stop |
| T7 | `dir` change sur la bougie **en formation** uniquement | Aucune fermeture |
| T8 | Symbole refusé par le garde de péremption | Pas de sortie par direction ; le moniteur de protection surveille toujours stop / objectif |
| T9 | Même cycle exécuté deux fois | Une seule fermeture, une seule jambe de livre `close:`, trésorerie créditée une fois |
| T10 | Replay de 200 bougies synthétiques | Nombre de positions `SHORT` = 0 ; `sum(jambes du livre) == cash` (`reconcile` OK) |
| T11 | Portefeuilles `ICHIVOL_BASELINE_V1` et autres profils | Comportement **inchangé** sur les mêmes séquences (non-régression : `exit_mode`/`allow_short` par défaut) |

## 4. Valeurs de référence du banc de recherche (recalcul indépendant ichivol-36, un tirage seed 7, coûts de base 5 bps ; entre parenthèses scénario défavorable)

| Fenêtre | A (sortie décision, L+S) | E (sortie direction, L+S) | **E longs seuls** | Transactions E longs | Durée moy. E longs |
|---|---:|---:|---:|---:|---:|
| Développement | −2 564 | −750 | **−738** (−1 821) | 417 | 7,6 h |
| V1 | −533 | +1 151 | **+441** (+76) | 133 | 8,1 h |
| V2 | −1 172 | −324 | **−274** (−579) | 146 | 6,0 h |
| V3 | −202 | −13 | **+556** (+252) | 174 | 7,4 h |
| Validation | −1 817 | +475 | **+733** (−314) | 457 | 7,2 h |

Concordances avec l'étude d'ichivol-69 (10 tirages) : E longs seuls validation +719, E validation +475 ; le tirage seed 7 seul est +733. **Critère de conformité d'une implémentation sur les mêmes séries de signaux** : nombre de transactions de E longs à ±5 % de la référence (457 en validation), durée moyenne 6–9 h, aucun SHORT, 0 fermeture sur simple passage à WATCH ; l'écart de résultat net dépend du fill (voir §1, écart connu) et n'est **pas** un critère de réussite.

## 5. Ce que cette spécification ne prouve pas
E longs seuls reste négative sur le développement (−738 / −957 en moyenne de 10 tirages) et sur V2 ; le plan de suivi en avant existe précisément parce que l'historique ne suffit pas à décider (≥ 8 semaines, ≥ 150 transactions, critères fixés à l'avance).
