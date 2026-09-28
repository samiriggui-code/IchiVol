# RS-04 — Famille structurelle : configuration « BOS confirmé → retour → reprise » (SPÉCIFICATION, non exécutée)

**Statut :** proposition de configuration **unique**, pour avis et comparaison **après** RS-D1. Ce n'est **pas** un pré-enregistrement de run : il faudra un amendement séparé, avec ses paramètres figés, avant tout code de backtest.

## 1. L'idée en une phrase

Ne pas acheter **la cassure** (B7 et RS-D1 le font déjà), mais **le premier retour** du prix sur le niveau cassé ou dans le déséquilibre (FVG) laissé par la cassure, une fois que la reprise est confirmée. Le stop se place sous la structure qui vient de tenir.

## 2. Pourquoi l'information pourrait différer de B7

- B7 entre **après** une hausse d'environ 3 ATR (VP-P §3.2), sur une cassure Donchian, avec un stop à 1,5 ATR placé dans le bruit.
- Ici, on entre **plus bas**, sur un retracement, avec un stop **structurel** : sous le plus bas du retour, qui ne doit pas casser si la cassure était vraie. Le rapport gain / risque est donc construit **par la localisation**, pas par un objectif fixe.
- Cette configuration utilise des objets **que le paper n'exploite pas du tout** (RS-01) : BOS comme **déclencheur** (et pas seulement comme invalidation) et FVG comme **zone**.

## 3. Règles proposées (unité 4h, long seulement, tout sur barres closes)

| Étape | Règle | Calcul existant |
|-------|-------|-----------------|
| **Contexte** | HTF 1d close (§2.2) **≠ short** | `align_htf_directions` (VP3) |
| **Événement** | BOS **haussier confirmé** à la barre `b` (clôture au-delà du dernier swing high **confirmé**, déplacement ≥ 1 ATR) ; niveau cassé `N` | `indicators/structure.py` (`confirm_bars=1`, `confirm_displacement_atr=1.0`) |
| **Zone de retour** | `Z = [N − 0.25 ATR[b], N + 0.25 ATR[b]]` ∪ le FVG haussier **formé pendant l'impulsion de cassure** (connu à sa 3ᵉ bougie, **≤ barre de retour**) | `indicators/fvg.py` |
| **Validité** | Scénario ouvert pendant **12 barres** après `b` (48 h). Au-delà : annulé | — |
| **Annulation** | Avant l'entrée : `close < N − 1 × ATR` **ou** BOS **baissier** confirmé → annulé | `structure.py` |
| **Retour** | Première barre `r ∈ (b, b+12]` dont le `low` touche `Z` | — |
| **Déclencheur** | Première barre `c ∈ [r, r+3]` avec `close[c] > high[r]` (reprise) → entrée à `open(c+1)` | — |
| **Stop** | `min(low[r .. c]) − 0.5 × ATR[c]` | `indicators/atr.py` |
| **Sortie** | Stop suiveur **identique à RS-D1** (plus haute clôture − 3 ATR, montée seule), **ou** BOS **baissier** confirmé → sortie à l'open suivant | `structure.py` |
| **Taille / coûts / capital** | Identiques à RS-D1 (§5–§6), pour une comparaison propre | `research_lab/sim.py` + options #159 |

## 4. Garde-fous contre le subjectif et le futur

- **Trois dates par objet :** `t_graph` (pivot / bougie), `t_known` (confirmation : swing `j+2`, FVG 3ᵉ bougie, BOS à confirmation), `t_decide ≥ t_known`. Un FVG qui n'est pas encore connu à la barre `r` n'existe pas pour le scénario.
- **Aucune lecture d'un champ d'événement futur** : `filled`, `broken`, `swept` ne sont lus qu'à leur barre.
- **Fibonacci : non utilisé** dans cette configuration. S'il l'était, il faudrait un ancrage causal (impulsion confirmée de `indicators/impulse.py`), jamais un ancrage « à l'œil ».
- **Liquidité : non utilisée.** Les zones BSL / SSL sont **déduites des prix** (sommets égaux). Ce ne sont **pas** des ordres observés, et nous n'avons pas de carnet d'ordres historique.
- **Un seul scénario ouvert par actif.** Pas de cumul « BOS + CHOCH + FVG + Fib + liquidité » comme cinq votes.

## 5. Ce qui reste à formaliser avant un amendement

1. Définition exacte de « FVG formé pendant l'impulsion » : FVG dont la 3ᵉ bougie est dans `[swing low précédent, b]`.
2. Cas où plusieurs BOS se succèdent pendant la validité : **le plus récent remplace** le scénario ouvert.
3. Test de troncature au niveau du scénario : états « ouvert / annulé / déclenché » identiques avec ou sans données futures.
4. Critères de jugement : **les mêmes que RS-D1**, avec en plus **D8** = « RS-S1 bat RS-D1 » (bootstrap mensuel du Δ). Cela évite qu'une variante plus complexe soit retenue sans faire mieux que la référence simple.

## 6. Ordre

RS-S1 ne sera pré-enregistré qu'**après** le rapport RS-D1, que RS-D1 soit rejeté ou non. On n'ouvre pas une deuxième hypothèse avant d'avoir la conclusion de la première. Aucune variante de RS-S1 (12 barres, 0,25 ATR…) ne sera jouée sans nouvel amendement.
