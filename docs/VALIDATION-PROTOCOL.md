# VALIDATION-PROTOCOL — IchiVol (VP0)

**Statut :** DOC ONLY · gelé avant tout run · 2026-09-26  
**Tip référence :** `main` @ `6634438`  
**Version :** `VP0-2026-09-26`  
**Interdit :** code, runs Lab/backtest, régénération de goldens, trading réel, intervention Claude dans VP1→VP7.

> Toute modification **après** review Claude + utilisateur = **nouvelle version datée** (`VP0-YYYY-MM-DD`) avec justification (§12).  
> Annexe technique (lookahead, budgets runtime) : [`VP0-PROTOCOLE-VALIDATION.md`](./VP0-PROTOCOLE-VALIDATION.md) — **préconditions**, pas ce protocole.

---

## 1. Question centrale

Les informations en plus d’IchiVol (RVOL, OI, CVD, funding, MTF, régime, et le pipeline live) donnent-elles de **meilleures décisions** que des stratégies plus simples, **hors échantillon** et **après coûts** ?

Réponse attendue en trois verdicts figés (§9) : **EDGE** / **PAS D’EDGE** / **NON CONCLUANT**.

---

## 2. Échelle B0 → B8

Chaque niveau a des **règles d’entrée et de sortie** exactes. La **sortie commune** (§6) s’applique à tous sauf B0 (toujours investi). On ne saute pas de niveaux. B8 n’ajoute **jamais** plusieurs briques d’un coup.

| ID | Nom | Entrée (long seul) | Sortie | Paramètres figés |
|----|-----|--------------------|--------|------------------|
| **B0** | Buy & Hold | Toujours long dès la 1ʳᵉ barre éligible | Jamais (tenir jusqu’à fin de fenêtre) | — |
| **B1** | Ichimoku 9/26/52/26 | Close croise au‑dessus de Tenkan **et** prix au‑dessus du nuage (Senkou A/B) ; Tenkan > Kijun | Sortie commune (§6) **ou** close sous Kijun | `tenkan=9`, `kijun=26`, `senkou_b=52`, `displacement=26` |
| **B2** | B1 + RVOL SMA20 ≥ 1.5 | B1 **et** `rvol20 ≥ 1.5` (avg volume trailing 20 barres) | Idem B1 | B1 + `rvol_window=20`, `rvol_min=1.5` |
| **B3** | RVOL saisonnier | Comme B2 mais `rvol` = volume / moyenne **saisonnière** (même heure UTC / même jour de semaine sur lookback) | Idem B1 | **Après C1** (feature saisonnière livrée) ; sinon skip B3 |
| **B4** | Ichimoku + OI + CVD | B1 **et** OI en hausse vs barre N−1 **et** CVD aligné long (pression acheteuse) | Idem B1 | **Après C2** ; OI/CVD = providers live déjà câblés |
| **B5** | + MTF | B2 **et** direction HTF (4h si signal 1h ; 1d si signal 4h) ≠ short | Idem B1 | HTF = timeframe supérieur canonique Lab |
| **B6** | + régime | B5 **et** régime ATR/ADX **pas** `dead` / `extreme` (mêmes seuils pipeline live) | Idem B1 | Seuils `LiveScreenerSettings` / ATR production |
| **B7** | IchiVol Core | Signal = pipeline live Option B (`build_pipeline` → BUY) | Sortie commune (§6) ; invalidation stages = flat | `strategy_version` tip gelé au run |
| **B8** | Full | **B7 + une seule** brique additionnelle mesurée (ex. funding, OB, PPO…) | Idem B7 | Ajouts **un par un** depuis B7 ; jamais pack |

**Règle d’arrêt :** si Bi n’améliore pas Bi−1 sous §9 sur les plis de test WF (§5), on ne revendique pas Bi+1 pour ce symbole/TF.

---

## 3. Questions A → L

Si l’utilisateur fournit une liste A–L d’origine, **elle remplace** celle-ci. Sinon :

| Q | Comparaison exacte | Métrique décisive | Étape VP |
|---|--------------------|-------------------|----------|
| **A** | B1 vs B0 | Espérance nette / trade + Deflated Sharpe | **VP3** |
| **B** | B2 vs B1 | Δ espérance nette ; IC bootstrap du Δ | **VP3** |
| **C** | B3 vs B2 | Δ espérance nette (après C1) | **VP5** |
| **D** | Ablation de chaque brique de B7 (leave-one-out) | Δ espérance / Deflated Sharpe vs B7 full | **VP6** |
| **E** | Apport OI (B4 sans OI vs avec OI, ou ablation OI dans B7) | Δ espérance nette | **VP5** |
| **F** | Apport CVD | Δ espérance nette | **VP5** |
| **G** | Apport funding | Δ espérance nette | **VP5** |
| **H** | B5 vs B2 | Δ espérance nette + Calmar | **VP3** |
| **I** | Redondance / corrélation des briques (signaux booléens) | Corrélation / VIF ; briques redondantes → candidat retrait | **VP6** |
| **J** | B7 vs meilleur de B0–B6 | Espérance nette, Deflated Sharpe, maxDD | **VP3** |
| **K** | Stabilité par régime et par actif | Même signe d’espérance sur ≥ 2/3 des régimes × actifs | **VP7** |
| **L** | Holdout 2026 (une fois) + 3 mois paper forward | Critères §9 sur holdout **et** paper | **VP7** |

---

## 4. Données

| Champ | Valeur |
|-------|--------|
| Symboles | **BTCUSDT**, **ETHUSDT**, **SOLUSDT** spot |
| Timeframes | **1h**, **4h** |
| Fenêtre | **2020-09-01** → **2026-08-31** (UTC, bougies **clôturées**) |
| Source | `data.binance.vision` (klines spot) |
| Intégrité | Manifeste **sha256** par fichier (livré en **VP1**, avant tout run) |

Pas de Twelve Data / proxy live pour les runs VP (crédits + non-reproductibilité).

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

**Note B7 / 2026 :** 2026 a déjà été vu par le pipeline live → pour B7, le holdout historique n’est **pas** un vrai hors-échantillon. Le **paper forward ≥ 3 mois** (§3 L) est le seul OOS crédible pour B7.

Warm-up indicateurs : exclure les barres sans Ichimoku/RVOL complets (min ~52+26 barres) du score, mais les garder en contexte.

---

## 6. Exécution (commune à B1–B8)

| Paramètre | Valeur gelée |
|-----------|--------------|
| Direction | **Long seul** (shorts off) |
| Décision | À la **clôture** de la barre signal |
| Fill | **Ouverture** de la barre suivante (pas de fill intra-barre) |
| Capital initial | **10 000** unités quote (USDT) — identique pour toutes les strates |
| Taille | 100 % du cash disponible à l’entrée (1 position max) — pour comparer les **règles**, pas le money management |
| **Stop** | `1.5 × ATR(14)` sous le low de la barre signal (distance stop = `1.5 * atr`) |
| **Take-profit** | **2R** (2 × distance entrée→stop) |
| **Time-stop** | **48** barres (1h) / **24** barres (4h) si ni SL ni TP |
| Slippage fill | Profils coûts §7 (pas de fill « mid » gratuit) |

B0 ignore stop/TP/time-stop (toujours long).

---

## 7. Coûts

Aujourd’hui divergence : Lab backtest ≈ **5 + 3 bps/côté** (commission+slippage confondus) ; `research_lab` = **5 + 2 + 3** (commission + spread + slippage).

**Décision VP0 — profil de base unifié :** aligné `research_lab.BASE_COST` / `ICHIVOL_BASELINE_V1` :

| Profil | Commission / côté | Spread / côté | Slippage / côté | Total / côté |
|--------|-------------------|---------------|-----------------|--------------|
| **Base** | 5 bps | 2 bps | 3 bps | **10 bps** |
| **Défavorable** | 10 bps | 4 bps | 8 bps | **22 bps** (+ financement short N/A car long-only) |

Les trois composantes sont **comptées et reportées séparément** dans les métriques (§8). Round-trip = 2 × (commission + spread + slippage) en bps sur notionnel.

Tout run VP doit déclarer le profil (`base` | `adverse`). Le verdict §9 se juge d’abord sur **base** ; **adverse** est un stress (EDGE qui disparaît en adverse → **NON CONCLUANT** ou **PAS D’EDGE** selon §9).

---

## 8. Métriques (par pli et par régime)

Toutes **nettes de coûts** sauf mention contraire.

| Métrique | Note |
|----------|------|
| Net P&amp;L | Absolu + % capital |
| CAGR | Annualisé sur la fenêtre du pli |
| Max drawdown | Peak-to-trough equity |
| Sharpe | rf = 0, barre → annualisation √N |
| Sortino | Idem downside |
| Calmar | CAGR / \|maxDD\| |
| Profit factor | Gains bruts / \|pertes brutes\| |
| Espérance / trade | **Critère principal** (net) |
| Win rate | **Jamais** critère principal — reporté seulement |
| Gain moyen / perte moyenne | |
| Nombre de trades | |
| Exposition | % barres en position |
| Turnover | Notionnel tradé / capital |
| Frais commission payés | Séparé |
| Spread payé | Séparé |
| Slippage payé | Séparé |

Régimes : buckets ATR/ADX pipeline (`dead` / `normal` / `trending` / `extreme`) — mêmes labels live.

---

## 9. Critères de verdict (fixés à l’avance)

Jugés sur les **plis de test WF** (agrégat), puis confirmés en **validation 2025**. Holdout / paper = VP7.

| Verdict | Conditions (toutes requises sauf NON CONCLUANT) |
|---------|--------------------------------------------------|
| **EDGE** | (1) Espérance nette / trade **> 0** sur agrégat WF ; (2) IC bootstrap 95 % de l’espérance **exclut 0** ; (3) **Deflated Sharpe > 0** (Bailey & López de Prado, avec N essais = compteur T10b §10) ; (4) Espérance **> 0** sur **≥ 5 / 7** plis WF ; (5) **N trades ≥ 40** sur agrégat WF (symbole×TF) ; (6) maxDD **< 35 %** sur chaque pli WF |
| **PAS D’EDGE** | N ≥ 40 **et** (espérance ≤ 0 **ou** Deflated Sharpe ≤ 0 **ou** < 3/7 plis positifs) |
| **NON CONCLUANT** | N < 40, **ou** IC bootstrap trop large (inclut 0) avec Sharpe borderline, **ou** EDGE en base mais **PAS D’EDGE** en adverse, **ou** instabilité extrême (signe inverse sur > 3 plis) |

Le **win rate n’entre pas** dans le verdict.

Comparaisons A–L « Bi bat Bj » : EDGE sur le **Δ** d’espérance (IC du Δ exclut 0) **et** Deflated Sharpe du Δ > 0, sinon PAS D’EDGE / NON CONCLUANT selon N.

---

## 10. Budget d’essais (T10b)

- Chaque run VP (chaque couple strate×symbole×TF×profil×pli agrégé enregistré) **incrémente** le compteur `hypothesis_id` / lineage T10b (`strategy_lab` Perf DB).
- Le **Deflated Sharpe** utilise ce N d’essais (pas un N inventé après coup).
- **Interdiction** de régler un paramètre (Ichimoku, RVOL min, ATR mult, TP R, time-stop, coûts) en regardant un pli de **test**, la **validation 2025**, ou le **holdout**.
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

## Carte VP1 → VP7 (exécution, hors de ce ticket)

| Étape | Contenu | Débloque |
|-------|---------|----------|
| **VP1** | Download + manifeste sha256 + loader figé | Données |
| **VP2** | Harness exécution commune (§6–§7) branché Lab | Runs |
| **VP3** | B0–B2, B5, B7 + questions A, B, H, J | Première lecture edge |
| **VP4** | (réservé) rapport intermédiaire / UI lecture seule | — |
| **VP5** | B3/B4 + E/F/G (après C1/C2) | Microstructure |
| **VP6** | Ablation B7 + redondance (D, I) | ADN |
| **VP7** | Stabilité régimes (K) + holdout une fois + paper 3 mois (L) | Promo / stop |

**AW0** (consolidation assemblages) = doc only **après** gel de ce protocole ; code AW1+ **après** déblocage VP.

---

*Fin VALIDATION-PROTOCOL `VP0-2026-09-26` — DOC ONLY.*
