# RS-05 — Piste RS-U « Ouverture US (09:30 New York) » : porte descriptive RS-U0, règles et critères figés

**Statut :** **pré-enregistré avant tout téléchargement 5 min et tout calcul** · amendement `VP0-2026-09-28c` (Question RS-U) · pilote Claude local · 2026-09-28.
**Origine :** concept vu en vidéo (« je ne trade qu'à 15h30 ») : range pré-session → balayage (sweep) d'un extrême à l'ouverture US → retournement → entrée contraire, stop au-delà de l'extrême, objectif de l'autre côté.
**Hypothèse économique :** l'ouverture cash US concentre volume et volatilité. Un balayage du range pré-session à ce moment serait plus souvent une **prise de liquidité suivie d'un retournement** qu'à une autre heure.

**Ce que RS-U n'est pas :**
- **ni** un filtre horaire sur B7 : B7 décide en 1h / 4h clôturées, et la bougie 4h 12:00–16:00 UTC contient déjà l'ouverture ;
- **ni** une stratégie : RS-U0 est une **mesure** qui décide si une stratégie intraday mérite d'être spécifiée (RS-U1) ;
- **ni** un empilement de confirmations (RVOL, VWAP, CVD, ADX, Ichimoku…). Chacune viendrait **après** RS-U1, une par amendement.

**Priorité :** RS-D1 reste prioritaire. RS-U0 est une mesure courte, sans moteur ni simulation de portefeuille, qui ne bloque pas RS-D1.

---

## 1. Données et fenêtres

| Élément | Valeur figée |
|---------|--------------|
| Actifs | BTCUSDT, ETHUSDT, SOLUSDT **spot** |
| Série | Klines **5 min** Binance spot, archives mensuelles `data.binance.vision` (même source que VP1), **checksum `.CHECKSUM` vérifié** pour chaque zip, sha256 consignés dans un manifeste. Extension de données **propre à RS-U0** : VP1 (1h / 4h / 1d) n'est pas modifié |
| Fenêtre | **2021-07-01 → 2024-12-31** (période de développement). Troncature au chargement `open_time < 2025-01-01T00:00Z`, **assertion** obligatoire |
| Jours retenus | Jours de **séance NYSE** (lundi–vendredi hors fériés NYSE, liste §7). Les demi-séances comptent (l'ouverture a lieu) |
| Interdit | Validation 2025, holdout 2026, toute autre source, toute variante des paramètres §2–§3 |
| Trous | Un ancrage dont une barre de la fenêtre pré-session, de la fenêtre de balayage ou de l'horizon manque est **exclu** (compté dans `n_excluded`) |

## 2. Ancrages (l'heure est une variable, pas une constante)

- **Ancrage testé `A*`** = **09:30 America/New_York**, converti en UTC jour par jour (`zoneinfo`). C'est **13:30 UTC** en heure d'été US et **14:30 UTC** en heure d'hiver. On n'utilise **pas** « 15h30 Paris » : les changements d'heure US et UE ne tombent pas le même jour.
- **Ancrages placebo** : les **48 demi-heures** de la journée NY (00:00, 00:30 … 23:30, heure locale NY), mêmes jours NYSE, même définition. `A*` en fait partie. Les 47 autres forment la distribution de référence.
- Question posée : **09:30 NY se distingue-t-il des 47 autres demi-heures ?**

## 3. Définitions (identiques pour chaque ancrage `A`)

Barres 5 min indexées par leur `open_time`. La barre `A` est celle qui s'ouvre à `A`.

- **Range pré-session** (longueur fixe, pour que tous les ancrages soient comparables) :
  - `RH = max(high)` et `RL = min(low)` des **72 barres** `[A − 6h, A)`.
- **Fenêtre de balayage** : les **3 barres** `A`, `A+5`, `A+10` (15 minutes).
- **Balayage haussier** : la première barre `b` de la fenêtre où `high[b] > RH`.
  - **Confirmation** : la première barre `c ≥ b` de la fenêtre où `close[c] < RH`.
  - Signal **SHORT** (`s = −1`).
- **Balayage baissier** : symétrique (`low[b] < RL`, puis `close[c] > RL`).
  - Signal **LONG** (`s = +1`).
- **Ambiguïtés** :
  - si une même barre dépasse **RH et RL**, l'ancrage est classé `ambigu`, sans événement ;
  - si les deux côtés sont balayés sur des barres différentes, seul le **premier** balayage est retenu, et sa confirmation doit venir avant tout balayage de l'autre côté.
- **Pas de confirmation** dans la fenêtre : `sweep_sans_retour` (compté, sans événement).
- **Entrée théorique** : `open[c+1]`, soit la barre suivant la confirmation.
- **Horizon** : **12 barres** (60 min). Sortie théorique `open[c+13]`.
- **Rendement signé brut** : `r = s × (open[c+13] / open[c+1] − 1)`, en bps.
- **Coût aller-retour paper** : `2 × (7,5 + friction)` bps, soit **17** (BTC), **17** (ETH) et **18** (SOL). Rendement net `r_net = r − coût`.
- **MAE / MFE** (descriptifs) : excursion adverse et favorable maximale entre `c+1` et `c+12`, en multiples de la distance `|open[c+1] − extrême du balayage|`, c'est-à-dire en R d'un stop placé à l'extrême.

Pas de stop, pas d'objectif, pas de taille : RS-U0 **mesure un rendement conditionnel**. Ce n'est pas une simulation.

## 4. Mesures par actif × ancrage

| Mesure | Définition |
|--------|------------|
| `vol15` | Médiane de `(max high − min low) / open[A]` sur les 3 barres de la fenêtre, en bps |
| `volshare15` | Médiane du volume des 3 barres / volume moyen de 3 barres sur les 24 h précédentes |
| `n_evt` | Nombre d'événements confirmés (LONG + SHORT) |
| `p_evt` | `n_evt / jours valides` |
| `mean_net` | Moyenne de `r_net` |
| `hit` | Part de `r > 0` |
| `IC95(mean)` | Bootstrap **par jour** (on tire des jours entiers), 10 000 tirages, seed 7, percentile |
| `rank_net` | Rang de `A` parmi les 48 ancrages par `mean_net` décroissant (1 = meilleur) |

## 5. Critères de la porte RS-U0 (figés avant tout calcul)

| # | Critère (par actif) |
|---|---------------------|
| **G1** | Contrôle de cohérence, **non bloquant** : `vol15(09:30)` parmi les 3 plus élevés des 48 ancrages. S'il échoue, le prémisse « l'ouverture est spéciale » est déjà faux et le rapport le dit |
| **G2** | `mean_net(09:30) > 0` **et** borne basse de `IC95` de la moyenne **brute** `> 0` |
| **G3** | Spécificité : `rank_net(09:30) ≤ 5` sur 48, soit le premier décile environ |
| **G4** | `n_evt(09:30) ≥ 100` (sinon NON CONCLUANT pour l'actif) |

**Verdict :**
- **PASSE** : G2, G3 et G4 vrais sur **≥ 2 des 3** actifs. Cela autorise **seulement** la rédaction de RS-U1, une simulation de portefeuille avec stop, objectif, coûts paper et adverses et références, sous un **nouvel** amendement pré-enregistré.
- **ÉCHEC** : G4 vrai sur ≥ 2 actifs, et G2 ou G3 faux sur ≥ 2 actifs. La piste RS-U est **close** telle quelle.
- **NON CONCLUANT** : tous les autres cas, en particulier G4 faux sur ≥ 2 actifs.

**Garde-fou post-hoc :** changer après lecture la longueur du range (6 h), la fenêtre (15 min), l'horizon (60 min), la définition du balayage, ou basculer vers la **continuation** (`−r`) produit une **nouvelle** hypothèse. Elle doit être marquée **post-hoc** dans le ledger, ne peut pas être jugée sur les mêmes données de développement, et relève d'une décision de Samir.

## 6. À reporter (descriptif, obligatoire)

- Tableau 48 ancrages × 3 actifs : `vol15`, `volshare15`, `p_evt`, `mean_net`, `hit`, `n_evt`.
- Pour 09:30 : ventilation LONG / SHORT, par année (2021 S2, 2022, 2023, 2024), par tercile de `vol15` du jour et par heure d'été ou d'hiver US.
- Distribution MAE / MFE en R pour 09:30.
- Comparaison **descriptive** « 15h30 Paris fixe » contre 09:30 NY sur les semaines où les deux diffèrent (fin mars et fin octobre / début novembre).
- `n_excluded`, `ambigu` et `sweep_sans_retour` par actif.
- Manifeste des zips (URL, sha256, checksum Binance).

## 7. Fériés NYSE exclus (fermetures complètes, 2021-07 → 2024-12)

- **2021 :** 07-05, 09-06, 11-25, 12-24
- **2022 :** 01-17, 02-21, 04-15, 05-30, 06-20, 07-04, 09-05, 11-24, 12-26
- **2023 :** 01-02, 01-16, 02-20, 04-07, 05-29, 06-19, 07-04, 09-04, 11-23, 12-25
- **2024 :** 01-01, 01-15, 02-19, 03-29, 05-27, 06-19, 07-04, 09-02, 11-28, 12-25

## 8. Contrôles d'implémentation exigés avant le calcul

1. Assertion : aucune barre ≥ 2025-01-01 chargée.
2. Tests unitaires :
   - conversion 09:30 NY → UTC sur une date d'été et une date d'hiver, et sur les semaines de décalage US / UE ;
   - range calculé sur `[A−6h, A)`, barre `A` exclue ;
   - balayage et confirmation ;
   - cas ambigu ;
   - entrée à `open[c+1]` et sortie à `open[c+13]` ;
   - coûts par symbole.
3. Causalité : le signal d'un ancrage ne dépend d'aucune barre postérieure à `c`, vérifié par troncature de la série à `c`.
4. Code **isolé** (`ichivol-app/engine/rs/us_open/`), sans aucun changement du paper, du pipeline ni de VP1.

## 9. T10b

+1 ligne `RS-U0-U3-5m` (porte descriptive, une hypothèse testée : 09:30 NY ; les 47 autres ancrages sont des placebos, pas des essais). Pas de DSR. RS-U1, s'il existe, sera une ligne distincte.
