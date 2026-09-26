# VP — Protocole de validation IchiVol (document only)

**Statut :** VP0 · docs only · 2026-09-26 · tip référence `6634438`  
**Source :** plan V3 (sections VP) + Lab existant (`ablation_oos`, T10e, T12 ADN)  
**Interdit ici :** code, runs, régénération de goldens, trading réel.

Ce document **décide avant les runs** : échelle de baselines, split IS/OOS, coûts, métriques, critères accept/reject, et les questions A–L.  
VP1+ = exécution (scripts / fixtures) **après** review Claude de ce protocole.

---

## 0. Principes non négociables

1. **Moteur Python = vérité.** Le LLM n’invente aucune valeur (prix, RVOL, période, niveau).
2. **Bougies clôturées uniquement.** Pas de lookahead, pas de repaint.
3. **Aucun indicateur ajouté** sans backtest / ablation OOS.
4. **Observe-only** tant que non promu : `promote_to_decision=false` ; ne mute pas `decision/` ni `paper/`.
5. **Critères figés avant le run.** Si un seuil change après avoir vu les résultats → run invalidé (re-baseline).
6. **GEL amont :** Chart Intelligence + T-CYCLE gelés (bugs only) jusqu’à déblocage VP.

---

## 1. Échelle de baselines B0 → B8

Chaque strate **ajoute** une capacité. On ne saute pas de B0 à B8. Un claim « Full ADN » doit battre **toutes** les strates inférieures sur le même split / mêmes coûts.

| ID | Nom | Définition opérationnelle (Lab) | Ce qu’on mesure |
|----|-----|----------------------------------|-----------------|
| **B0** | Buy & Hold | Toujours long sur la série (réf. T12c `run_reference_baselines`) | Exposition, CAGR/vol, drawdown |
| **B1** | Donchian breakout | Règle Donchian fixe (réf. T12c) | Trades, PF, Δ vs B0 |
| **B2** | Structure BOS | Entrées sur BOS consensus (réf. T12c) | Idem + taux faux breaks |
| **B3** | Ichimoku seul | Pipeline / ruleset couche Ichimoku only | Δ expectancy vs B0–B2 |
| **B4** | Ichimoku + RVOL | ADN « B » (`rvol_min` = LiveScreenerSettings) | Participation gate |
| **B5** | + Location | B4 + filtre location (VP/VWAP/S/R proximity) | Qualité d’emplacement |
| **B6** | + Régime | B5 + ATR regime / ADX (si PRODUCTION) | Dead/extreme skip |
| **B7** | + MTF | B6 + alignement TF supérieur | Contre-tendance refusée |
| **B8** | Full | Pipeline Option B complet (stages live) | Claim « production candidate » |

**Règle d’arrêt :** si Bi n’améliore pas Bi−1 sous les critères §4 sur **OOS**, on ne monte pas à Bi+1 pour ce symbole/TF.

---

## 2. Split IS / OOS figé

Décidé **avant** tout run VP1. Ne pas retoucher après avoir vu les métriques.

| Paramètre | Valeur VP0 (proposition) | Notes |
|-----------|--------------------------|--------|
| Univers minimal | BTCUSDT, ETHUSDT | Étendre après 1er passage vert |
| Timeframe | `1h` (primaire) ; `4h` secondaire | Même protocole, runs séparés |
| Histoire | Deep history versionnée (T12a) si dispo ; sinon max Vision | Documenter `n_bars` + source |
| **IS** | 70 % chronologique du début | Walk-forward *expanding* ou *rolling* — choisir **un** mode et le figer |
| **OOS** | 30 % fin de série | Jamais utilisé pour choisir les hyperparams |
| Folds WF | ≥ 5 plis OOS (aligné T9g) | `min_oos_trades` défaut **30** (`min(base,var)`) |
| Purge | 1 horizon de trade entre IS et OOS | Évite overlap de labels |

**Interdit :** optimiser sur OOS puis « valider » sur le même OOS ; cherry-pick de fenêtres après coup.

---

## 3. Coûts séparés (fees + slippage)

Toujours reporter **deux** lignes de PnL :

| Composante | Défaut VP0 | Usage |
|------------|------------|--------|
| **Fees** | 4 bps round-trip (spot-like) | Coût « normal » |
| **Slippage** | 2 bps / fill (entrée+sortie = 4 bps) | Séparé des fees |
| **Adverse** | Fees 10 bps + slip 8 bps (aligné T9g) | Gate robustesse |

- Métriques « net » = gross − fees − slippage (ligne par ligne).  
- Un run **PASS** sous coûts normaux mais **FAIL** sous adverse → `inconclusive` / pas de promo (sauf justification écrite Claude).

---

## 4. Métriques & critères (figés avant runs)

### 4.1 Métriques obligatoires (par strate Bi, IS et OOS)

| Métrique | Définition |
|----------|------------|
| `n_trades` | Nombre de trades (OOS ≥ `min_oos_trades`) |
| `expectancy` | Espérance nette / trade |
| `PF` | Profit factor net |
| `max_dd` | Max drawdown equity |
| `Δ_exp` | expectancy(Bi) − expectancy(Bi−1) **ou** vs B0 si i=1 |
| `fold_winrate` | Fraction de plis OOS avec Δ_exp > 0 |
| `exposure` | Fraction du temps en position |

### 4.2 Acceptation / rejet (décidés maintenant)

| Verdict | Conditions (toutes requises pour PASS) |
|---------|----------------------------------------|
| **PASS** | OOS `n_trades` ≥ 30 ; `fold_winrate` > 0.5 (majorité stricte) ; Δ_exp OOS > 0 vs strate de référence ; PF OOS Δ ≥ 0 ; **et** Δ_exp > 0 sous coûts **adverse** |
| **INCONCLUSIVE** | PASS sous coûts normaux mais FAIL adverse ; **ou** `n_trades` OOS ∈ [15, 30) ; **ou** un seul symbole PASS |
| **REJECT** | Δ_exp OOS ≤ 0 vs référence ; **ou** lookahead / fuite détectée ; **ou** goldens / anti-repaint cassés |

**Promo feature / decision :** hors VP0 — voir `docs/research/PROMOTION-CRITERIA.md` (T10e). VP ne mute jamais le registre.

---

## 5. Questions A–L (checklist avant / après run)

Répondre **par écrit** dans le HANDOFF du run VP1+. Une case vide = run non clos.

| # | Question |
|---|----------|
| **A** | Quelle hypothèse exacte est testée (une phrase, falsifiable) ? |
| **B** | Quelle strate B0–B8 et quelle référence (Bi−1 ou B0) ? |
| **C** | Symboles / TF / `n_bars` / provider / tip git / RELEASE VPS ? |
| **D** | Split IS/OOS et mode WF (rolling vs expanding) — inchangés vs §2 ? |
| **E** | Fees / slippage / adverse — valeurs numériques utilisées ? |
| **F** | Critères PASS/INCONCLUSIVE/REJECT — ceux de §4.2 sans modification post-hoc ? |
| **G** | Bougies clôturées + pas de lookahead (tests / smoke) ? |
| **H** | Null models / baselines : lesquels (B&H, Donchian, BOS, shuffle…) ? |
| **I** | Combien de plis OOS verts ? `n_trades` OOS ? |
| **J** | Résultat sous coûts adverse : PASS / FAIL ? |
| **K** | Y a-t-il un effet de redondance vs feature PRODUCTION (T10c) ? |
| **L** | Décision : stop / itérer Bi / documenter pour T10e — **sans** merger de feature CI/T-CYCLE ? |

---

## 6. Liens Lab existants (réemploi VP1)

| Besoin | Module / doc |
|--------|----------------|
| Walk-forward | `strategy_lab/walk_forward.py` |
| Ablation × OOS | `strategy_lab/ablation_oos.py` + T9g-fix |
| Références B0–B2 | `run_reference_baselines_on_candles` (T12c) |
| ADN Ichimoku/RVOL | `ETUDE-T12-ADN-ICHIVOL.md` |
| Promo humaine | `research/PROMOTION-CRITERIA.md` |
| Cycle observe-only | `CYCLE_ENGINE_AUDIT.md` — **pas** de vote tant que OOS multi-symbol absent |

---

## 7. Hors scope VP0

- Implémentation / scripts / jobs CI
- Nouveaux indicateurs, producteurs ChartObject, pages UI
- AW1+ (explain, profils, OB, scénarios) — **interdit** tant que VP n’a pas débloqué
- Trading réel / broker
- Régénération GOLDEN-RVOL sans justification (voir §8)

---

## 8. Dépendance GOLDEN-RVOL

Sur tip agent/CI (`6634438`) : goldens RVOL **verts** (sha seed_42 `20e5f00266862b9f`).  
Issue [#135](https://github.com/samiriggui-code/IchiVol/issues/135).  
Si Claude reproduit un échec local → bisect + fix **ou** PR goldens dédiée avec diff de valeurs — **jamais** de skip silencieux. Bloque la confiance VP1 sur RVOL jusqu’à alignement des environnements.

---

## 9. Prochaine étape

1. Review Claude de **ce** protocole (seuils B0–B8, split, adverse).  
2. VP1 = runbook exécutable calé sur §1–5 (toujours docs+scripts, pas de feature CI/T-CYCLE).  
3. AW0 consolidation (doc) en parallèle de VP2 **après** validation du protocole.
