# VALIDATION-PROTOCOL — IchiVol (VP0)

**Statut :** DOC ONLY · gelé avant tout run · 2026-09-26  
**Tip référence :** `main` @ `c46eda1` (review Claude @ `6634438` ; GOLDEN-RVOL #139 mergé)  
**Version :** `VP0-2026-09-26` (corrections Claude pre-gel : Univers VP, §1ter sim, B1 TK, Sortino, bootstrap barre, carte VP3–VP9)  
**Interdit :** code, runs Lab/backtest, régénération de goldens, trading réel, intervention Claude dans VP1→VP7.

> Toute modification **après** review Claude + utilisateur = **nouvelle version datée** (`VP0-YYYY-MM-DD`) avec justification (§12).  
> Annexe technique (lookahead, budgets runtime) : [`VP0-PROTOCOLE-VALIDATION.md`](./VP0-PROTOCOLE-VALIDATION.md) — **préconditions**, pas ce protocole.

---

## 1. Question centrale

Les informations en plus d’IchiVol (RVOL, OI, CVD, funding, MTF, régime, et le pipeline live) donnent-elles de **meilleures décisions** que des stratégies plus simples, **hors échantillon** et **après coûts** ?

Réponse attendue en trois verdicts figés (§9) : **EDGE** / **PAS D’EDGE** / **NON CONCLUANT**.

---

## 1bis. Univers VP (config univers — figé)

Tout run VP cite **Univers VP**. Un autre univers = autre hypothèse + nouvel `hypothesis_id` (§10).

| Champ | Valeur Univers VP |
|-------|-------------------|
| Univers | `BTCUSDT`, `ETHUSDT`, `SOLUSDT` |
| Exécution | **Spot** long-only (§6) |
| TF signal | **1h** et **4h** (runs séparés) |
| TF HTF | **4h** si signal 1h ; **1d** si signal 4h (§4, §2 B5) |
| Fenêtre | 2020-09-01 → 2026-08-31 UTC |
| Capital | 10 000 USDT / strate |
| Coûts | profil **base** pour le verdict ; **adverse** = stress (§7, §10) |
| Sortie | **uniquement** sortie commune §6 (sauf B0) |

---

## 1ter. Simulateur de référence

Simulateur = `research_lab/sim.py` (S1), seul simulateur autorisé pour VP. Réglages figés : `allow_short=False` ; immediate_fill interdit ; plafonds portefeuille (risque 1 %, notionnel 25 %, daily halt, open-risk) neutralisés pour appliquer §6 (100 % cash, 1 position) ; seed d'ordonnancement figée ; chaque sortie de run contient seed, sha256 des données (manifeste VP1), version du protocole et profil de coûts. Les biais de S3 (`docs/VP2-AUDIT-BANC.md`) rendent les anciens verdicts Lab/ADN non comparables.

---

## 2. Échelle B0 → B8

Chaque niveau a des **règles d’entrée** exactes. La **sortie** de B1–B8 est **strictement** la sortie commune (§6) — **aucune** sortie « maison » (pas de close sous Kijun, pas d’invalidation ad hoc hors §6). On ne saute pas de niveaux. B8 n’ajoute **jamais** plusieurs briques d’un coup.

| ID | Nom | Entrée (long seul) | Sortie | Paramètres figés |
|----|-----|--------------------|--------|------------------|
| **B0** | Buy & Hold | Toujours long dès la 1ʳᵉ barre éligible (après warm-up) | Jamais (tenir jusqu’à fin de fenêtre) | — |
| **B1** | Ichimoku 9/26/52/26 | **Déclencheur événement** (§2.1) | **Sortie commune §6 uniquement** | `tenkan=9`, `kijun=26`, `senkou_b=52`, `displacement=26` |
| **B2** | B1 + RVOL SMA20 ≥ 1.5 | Déclencheur B1 **et** `rvol20 ≥ 1.5` sur la barre signal | §6 uniquement | B1 + `rvol_window=20`, `rvol_min=1.5` |
| **B3** | RVOL saisonnier | Comme B2 mais `rvol` = volume / moyenne **saisonnière** (même heure UTC / même jour de semaine sur lookback) | §6 uniquement | **Après C1** ; sinon skip B3 |
| **B4** | Ichimoku + OI + CVD | Déclencheur B1 **et** OI perp en hausse vs barre N−1 **et** CVD aligné long | §6 uniquement | **Après C2** ; OI = **perp** (§4) |
| **B5** | + MTF | B2 **et** HTF **fermée** ≠ short (§2.2) | §6 uniquement | HTF : 4h←1h, 1d←4h |
| **B6** | + régime | B5 **et** régime ATR/ADX **pas** `dead` / `extreme` (seuils pipeline live) | §6 uniquement | `LiveScreenerSettings` / ATR production |
| **B7** | IchiVol Core | Signal = pipeline live Option B (`build_pipeline` → BUY) sur barre **fermée** | §6 uniquement | `strategy_version` tip gelé au run |
| **B8** | Full | **B7 + une seule** brique additionnelle mesurée | §6 uniquement | Ajouts **un par un** depuis B7 |

**Règle d’arrêt :** si Bi n’améliore pas Bi−1 sous §9 sur les plis de test WF (§5), on ne revendique pas Bi+1 pour ce symbole/TF.

### 2.1 Déclencheur B1 (événement, pas état)

Sur la barre signal **clôturée** `t` :

1. **TK cross haussier :** `tenkan[t-1] ≤ kijun[t-1]` **et** `tenkan[t] > kijun[t]`.
2. **Filtre nuage :** `close[t] > max(SA_aff[t], SB_aff[t])`, où `SA_aff[t]` et `SB_aff[t]` sont les valeurs du nuage **AFFICHÉ** à `t`, c’est-à-dire calculées sur les données ≤ `t−26` (déplacement 26). Jamais de valeur calculée après `t`.
3. **Pas de chikou.**

Une entrée par cross ; pas de ré-entrée tant que la position est ouverte.

### 2.2 HTF fermée (B5+)

- La direction HTF est lue sur la **dernière bougie HTF entièrement close** à l’instant de décision du signal (pas de bougie HTF en formation).
- Mapping : signal **1h** → HTF **4h** ; signal **4h** → HTF **1d** (données 1d obligatoires, §4).
- Direction HTF = `close HTF > haut du nuage HTF affiché` → **long** ; `close HTF < bas du nuage HTF affiché` → **short** ; sinon **neutre**.
- Filtre B5+ : direction HTF **≠ short** (long ou neutre OK).

---

## 3. Questions A → L

Si l’utilisateur fournit une liste A–L d’origine, **elle remplace** celle-ci. Sinon :

| Q | Comparaison exacte | Métrique décisive | Étape VP |
|---|--------------------|-------------------|----------|
| **A** | B1 vs B0 | B0 = **equity** (§9.1) ; B1 = espérance/trade + DSR(B1) ; Δ via bootstrap **apparié** sur returns par barre (§9.2) | **VP3** |
| **B** | B2 vs B1 | Δ rendement moyen / barre + Δ Sharpe (IC apparié) ; DSR(B2) ≥ 0.95 (§9) | **VP3** |
| **C** | B3 vs B2 | Idem B (après C1) | **VP5** |
| **D** | Contribution de chaque brique de B7 **par ablation** | Δ barre apparié ; DSR(Bi) ; bootstrap apparié | **VP6** |
| **E** | Apport OI **perp** (B4 ± OI, ou ablation OI dans B7) | Δ barre ; IC apparié ; DSR(Bi) | **VP5** |
| **F** | Apport CVD | Idem E | **VP5** |
| **G** | Apport funding **perp** | Idem E | **VP5** |
| **H** | B5 vs B2 | Δ barre ; IC apparié ; DSR(Bi) | **VP3** |
| **I** | Redondance / corrélation des briques B7 | Corrélation signaux booléens ; redondance → candidat retrait | **VP6** |
| **J** | B7 vs meilleur de B0–B6 | Espérance reportée ; equity si vs B0 ; DSR(Bi) ; maxDD | **VP3** |
| **K** | Stabilité par régime et par actif | Même **signe** d’espérance (ou equity B0) sur régimes × actifs ; instabilité → NON CONCLUANT | **VP7** |
| **L** | Holdout 2026 (**une fois**) + **3 mois** paper forward | Critères §9 sur holdout **et** paper (B7 : paper = seul OOS crédible) | **VP7** |

---

## 4. Données

| Champ | Valeur |
|-------|--------|
| Symboles exécution | **BTCUSDT**, **ETHUSDT**, **SOLUSDT** **spot** |
| Timeframes signal | **1h**, **4h** |
| Timeframe HTF | **1d** (requis pour B5+ quand signal = 4h) + **4h** (HTF du 1h) |
| Fenêtre | **2020-09-01** → **2026-08-31** (UTC, bougies **clôturées**) |
| Source prix / volume spot | `data.binance.vision` — klines **spot** |
| Source OI / funding | `data.binance.vision` — **futures USDT-M perp** (même base symbol, série perp) ; jointure sur barre spot **fermée** (timestamp aligné, pas de lookahead) |
| CVD | Série dérivée / provider figé en VP1 (même discipline closed-only) |
| Intégrité | Manifeste **sha256** par fichier (livré en **VP1**, avant tout run) |

Pas de Twelve Data / proxy live pour les runs VP (crédits + non-reproductibilité).

**OI / funding = perp uniquement.** On n’invente pas d’OI spot. Les runs B4/E/G qui manquent de série perp complète sur la fenêtre → **skip** documenté (pas de substitut).

---

## 5. Plis (walk-forward / validation / holdout)

**Développement** : jusqu’au **2024-12-31**. Walk-forward **expanding train**, plis de **test = 6 mois** :

| Pli | Train (inclus) | Test (inclus) |
|-----|----------------|---------------|
| WF1 | 2020-09-01 → 2021-06-30 | 2021-07-01 → 2021-12-31 |
| WF2 | 2020-09-01 → 2021-12-31 | 2022-01-01 → 2022-06-30 |
| WF3 | 2020-09-01 → 2022-06-30 | 2022-07-01 → 2022-12-31 |
| WF4 | 2020-09-01 → 2022-12-31 | 2023-01-01 → 2023-06-30 |
| WF5 | 2020-09-01 → 2023-06-30 | 2023-07-01 → 2023-12-31 |
| WF6 | 2020-09-01 → 2023-12-31 | 2024-01-01 → 2024-06-30 |
| WF7 | 2020-09-01 → 2024-06-30 | 2024-07-01 → 2024-12-31 |

| Phase | Dates | Règle |
|-------|-------|-------|
| **Validation** | 2025-01-01 → 2025-12-31 | Une fois les règles B* figées après WF ; **interdit** de retuner |
| **Holdout** | 2026-01-01 → 2026-08-31 | Ouvert **UNE fois** |

### 5.1 Règles de plis (strictes)

1. **Expanding only** — pas de rolling train alternatif sans nouvelle version de protocole.
2. **Purge** — au moins **1 horizon time-stop** (48 barres 1h / 24 barres 4h) entre fin train et début test ; labels / positions ouvertes en train ne fuient pas dans le test.
3. **Warm-up** — barres sans Ichimoku/RVOL/ATR complets (min ~52+26) : hors score, gardées en contexte.
4. **Figé avant test** — aucun paramètre choisi en regardant le pli de test, la validation 2025, ou le holdout.
5. **Agrégat WF** — verdict §9 sur l’union des plis de **test** (pas le train).
6. **Symbole × TF** — chaque couple Univers VP est un run séparé ; pas de pooling pour le claim EDGE primaire.
7. **Appartenance pli** — un trade appartient au pli de sa barre d’entrée ; il peut se terminer après la fin du pli.
8. **Fin de fenêtre** — fin de validation 2025 et fin de holdout : sortie forcée au close de la dernière barre.
9. **Pli maigre** — un pli avec &lt; 5 trades ne compte pas comme pli positif (critère 4).
10. **Train = warm-up uniquement** — les paramètres étant fixés a priori, le « train » ne sert à aucun ajustement : il sert au warm-up et à la calibration saisonnière / régime uniquement.

**Note B7 / 2026 :** 2026 a déjà été vu par le pipeline live → pour B7, le holdout historique n’est **pas** un vrai hors-échantillon. Le **paper forward ≥ 3 mois** (§3 L) est le seul OOS crédible pour B7.

---

## 6. Exécution (commune à B1–B8) — sortie commune stricte

| Paramètre | Valeur gelée |
|-----------|--------------|
| Direction | **Long seul** (shorts off) |
| Décision | À la **clôture** de la barre signal |
| Fill entrée | **Ouverture** de la barre suivante |
| Capital initial | **10 000** USDT — identique pour toutes les strates |
| Taille | 100 % du cash disponible à l’entrée (1 position max) |
| **Stop (exact)** | `atr = ATR(14)` de la barre signal ; `entry = open(t+1)` ; `stop = entry − 1.5 × atr` |
| **Take-profit (exact)** | `risk = entry − stop` ; `tp = entry + 2 × risk` (**2R**) |
| **Time-stop (exact)** | **48** barres si TF signal = 1h ; **24** barres si TF signal = 4h ; sortie au **close** de la barre time-stop si ni SL ni TP touchés |
| Priorité sortie | Sur une barre : **stop avant TP** (conservateur) ; sinon time-stop en close |
| Slippage fill | Profils coûts §7 |
| Gap au-delà du stop/TP | Gap au-delà du stop ou du TP à l’ouverture → **fill à l’open** de cette barre |

**Sortie commune stricte :** B1–B8 sortent **UNIQUEMENT** par stop, TP ou time-stop ci‑dessus — **comme B1–B6**. Interdit : close sous Kijun, sous nuage, flip pipeline, « stages → flat », ou toute autre règle où un état du pipeline provoque une sortie. (B7 inclus : pas de sortie parallèle liée aux stages.)

B0 ignore stop/TP/time-stop (toujours long).

---

## 7. Coûts

Aujourd’hui divergence : Lab backtest ≈ **5 + 3 bps/côté** (commission+slippage confondus) ; `research_lab` = **5 + 2 + 3** (commission + spread + slippage).

**Décision VP0 — profil de base unifié :** aligné `research_lab.BASE_COST` / `ICHIVOL_BASELINE_V1` :

| Profil | Commission / côté | Spread / côté | Slippage / côté | Total / côté |
|--------|-------------------|---------------|-----------------|--------------|
| **Base** | 5 bps | 2 bps | 3 bps | **10 bps** |
| **Défavorable (adverse)** | 10 bps | 4 bps | 8 bps | **22 bps** |

Les trois composantes sont **comptées et reportées séparément** (§8). Round-trip = 2 × (commission + spread + slippage) en bps sur notionnel.

Tout run VP déclare le profil (`base` | `adverse`). Verdict §9 d’abord sur **base** ; **adverse** = stress (EDGE base qui disparaît en adverse → **NON CONCLUANT** ou **PAS D’EDGE** selon §9).

**Adverse ≠ nouvel essai (§10) :** rejouer la **même** hypothèse (mêmes B*, params, symbole, TF, plis) sous profil adverse **n’incrémente pas** le compteur T10b.

---

## 8. Métriques (par pli et par régime)

Toutes **nettes de coûts** sauf mention contraire.

### 8.1 Annualisation / Sortino (figés)

| TF | Barres / an `N_year` |
|----|---------------------|
| 1h | 365 × 24 = **8760** |
| 4h | 365 × 6 = **2190** |
| 1d | **365** |

- **Sharpe** (rf = 0) : `(mean(r) / std(r)) × √N_year` sur returns de barre (equity) **ou** annualisation trade documentée si série = trades (même `N_year` du TF signal).
- **Sortino** (rf = 0) : `downside_dev = sqrt(mean(min(r, 0)²))` sur **TOUTES** les barres (zéros et positifs compris, comptés 0) ; `Sortino = mean(r) / downside_dev × √N_year`. (La std des seules barres négatives — `app/backtest/metrics.py` — est **incorrecte** et n’est pas le Sortino VP.)
- **CAGR** : `(equity_end / equity_start) ^ (N_year / n_bars) − 1` sur la fenêtre du pli.

### 8.2 Table

| Métrique | Note |
|----------|------|
| Net P&amp;L | Absolu + % capital |
| CAGR | §8.1 |
| Max drawdown | Peak-to-trough equity |
| Sharpe | §8.1 |
| Sortino | §8.1 |
| Calmar | CAGR / \|maxDD\| |
| Profit factor | Gains bruts / \|pertes brutes\| |
| Espérance / trade | Critère principal **pour B1–B8** (net) |
| Win rate | **Jamais** critère principal — reporté seulement |
| Gain moyen / perte moyenne | |
| Nombre de trades | |
| Exposition | % barres en position |
| Turnover | Notionnel tradé / capital |
| Frais / spread / slippage | Séparés |

Régimes : buckets ATR/ADX pipeline (`dead` / `normal` / `trending` / `extreme`) — mêmes labels live.

---

## 9. Critères de verdict (fixés à l’avance)

Jugés sur les **plis de test WF** (agrégat), puis confirmés en **validation 2025**. Holdout / paper = VP7.

### 9.1 B0 jugé sur l’equity

B0 n’a **pas** de trades discrets. Pour B0 et pour toute comparaison impliquant B0 (question **A**, éventuellement **J**) :

- métriques = **CAGR equity**, **Sharpe equity**, **maxDD equity**, Sortino equity (§8.1) ;
- **pas** d’espérance / trade sur B0 ;
- Δ vs B0 : bootstrap **apparié** sur returns de **barre** (même indices).

### 9.2 Bootstrap apparié

Toute comparaison Bi vs Bj se fait sur les **rendements PAR BARRE** de l’equity des deux stratégies, sur les **mêmes barres** : block bootstrap stationnaire **apparié** (mêmes indices tirés pour Bi et Bj), bloc moyen **24** barres (1h) / **6** barres (4h), **10 000** tirages, seed figée. On compare le **Δ de rendement moyen par barre** et le **Δ de Sharpe** ; IC 95 % du Δ. L’espérance par trade reste **REPORTÉE** pour chaque B mais **ne sert pas** au test de Δ.

Pour l’IC de l’espérance d’**UNE** stratégie (critère EDGE 2) : bootstrap simple sur ses trades, 10 000 tirages, seed figée.

**Pas de « DSR du Δ ».** Pour une comparaison : IC apparié du Δ exclut 0 **et** DSR(Bi) ≥ 0.95.

### 9.3 DSR (Deflated Sharpe Ratio)

**DSR** = probabilité Bailey & López de Prado que le Sharpe vrai &gt; 0, avec `N` = compteur T10b (§10).

| Verdict | Conditions (toutes requises sauf NON CONCLUANT) |
|---------|--------------------------------------------------|
| **EDGE** | (1) Espérance nette / trade **> 0** sur agrégat WF (**sauf** jugements B0 → CAGR&gt;0 et Sharpe equity&gt;0) ; (2) IC bootstrap 95 % sur trades de **la** stratégie exclut 0 ; (3) **DSR(Bi) ≥ 0.95** ; (4) Espérance (ou CAGR B0) **> 0** sur **≥ 5 / 7** plis WF (pli &lt; 5 trades ≠ positif, §5.1) ; (5) **N trades ≥ 40** sur agrégat WF pour B1–B8 (symbole×TF) — N/A pour B0 seul ; (6) maxDD **&lt; 35 %** sur chaque pli WF (**B1–B8** ; **B0 exempté**, c’est le benchmark) |
| **PAS D’EDGE** | N trades ≥ 40 (B1–B8) **et** (espérance ≤ 0 **ou** DSR &lt; 0.95 **ou** &lt; 3/7 plis positifs) |
| **NON CONCLUANT** | N &lt; 40, **ou** IC apparié inclut 0, **ou** EDGE en base mais pas en adverse, **ou** instabilité (signe inverse sur &gt; 3 plis) |

Le **win rate n’entre pas** dans le verdict.

Comparaisons A–L « Bi bat Bj » : IC apparié du **Δ** (returns par barre) exclut 0 **et** DSR(Bi) ≥ 0.95 — **pas** de DSR du Δ. Sinon PAS D’EDGE / NON CONCLUANT selon N.

---

## 10. Budget d’essais (T10b)

- Chaque **nouvelle hypothèse** VP (nouvelle strate / params / symbole×TF / définition B*) **incrémente** le compteur `hypothesis_id` / lineage T10b.
- Le **DSR** utilise ce N d’essais (pas un N inventé après coup).
- **Adverse ≠ nouvel essai** : profil `adverse` sur la même hypothèse = stress **sans** incrément N.
- **Interdiction** de régler un paramètre en regardant un pli de **test**, la **validation 2025**, ou le **holdout**.
- Changement de paramètre = **nouvelle hypothèse** + nouvel `hypothesis_id` + bump version protocole si le contrat §2/§6 change.

---

## 11. Rôle de Claude

Claude **n’intervient pas** dans les runs **VP0→VP7** (moteur mesuré seul).

Claude + utilisateur : **review / gel** de ce document **avant VP1**.  
Après les runs : Claude peut lire les rapports chiffrés pour revue, **sans** retuner.

---

## 12. Versionnement

| Champ | Valeur |
|-------|--------|
| Version courante | `VP0-2026-09-26` |
| Gel | Après APPROUVÉ Claude **et** OK utilisateur |
| Modification post-gel | Nouveau fichier ou section `VP0-YYYY-MM-DD` + justification + invalidation des runs antérieurs non rejoués |

---

## Carte VP1 → VP9 (alignée roadmap V3 — ne pas redéfinir)

| Étape | Contenu (roadmap) | Questions | Débloque |
|-------|-------------------|-----------|----------|
| **VP0** | Ce protocole (DOC ONLY) | — | Gel |
| **VP1** | Download spot + **1d** + perp OI/funding ; manifeste sha256 ; loader figé | — | Données Univers VP |
| **VP2** | Harness exécution commune (§6–§7) + sortie stricte + coûts base/adverse ; simulateur §1ter | — | Runs reproductibles |
| **VP3** | B0, B1, B2, B5, B6, B7 → **A, B, H, J** (provisoires) | **A**, **B**, **H**, **J** | Première lecture edge |
| **VP4** | **SENSIBILITÉ** (RVOL 1.2→1.8, âge du TK cross, multiple ATR du stop), plis de **dev** uniquement, plateau vs pic isolé, aucun paramètre choisi sur le test | — | Robustesse params |
| **VP5** | B3, B4, funding → **C, E, F, G** | **C**, **E**, **F**, **G** | Microstructure / perp |
| **VP6** | Ablation + redondance → **D, I** | **D**, **I** | ADN |
| **VP7** | Régimes, holdout **une fois**, paper ≥ 3 mois → **K, L** | **K**, **L** | Promo / stop |
| **VP8** | Moteur seul vs moteur + Claude en shadow (si VP7 positif) | — | Shadow agent |
| **VP9** | Verdict par question, actif, TF | A–L | Synthèse |

**AW / AG (parallèle, hors runs VP) :** voir `AW0-CONSOLIDATION.md` §12 — AW1/AW3 et AG0–AG2 autorisés selon contrat ; AW5/AW6 interdits jusqu’au déblocage VP.

---

*Fin VALIDATION-PROTOCOL `VP0-2026-09-26` — DOC ONLY.*
