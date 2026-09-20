# ICHIVOL V2 — Roadmap (tranches implémentables)

**Date :** 2026-09-20  
**Audit :** [`ICHIVOL_V2_AUDIT.md`](./ICHIVOL_V2_AUDIT.md)  
**Handoff :** [`HANDOFF-CLAUDE-ALGOPRO-STRATEGY-LAB-2026-09-20.md`](./HANDOFF-CLAUDE-ALGOPRO-STRATEGY-LAB-2026-09-20.md)

Principe : **mesurable > démo**. Une tranche n’est done que si on peut répondre *pourquoi / quelle version / quel outcome*.

---

## Priorités alignées mission (P0→P5)

| P | Thème | Déjà en place ? | Action |
|---|--------|-----------------|--------|
| **P0** | Data quality, closed candles, decision stability, strategy_version, decision journal | Closed candles **EXISTE** ; version/journal **PARTIEL** | Durcir version + snapshot + journal |
| **P1** | Shadow / paper / outcome / metrics / MFE-MAE | Paper + outcomes **EXISTE** | Unifier shadow mode produit + A/B hooks |
| **P2** | Structure+, confluence familles, MTF, Risk engine | PARTIEL | Enrichir sans soup d’indicateurs |
| **P3** | Backtest rigoureux, ablation, WF, régimes | Lab **EXISTE** | Bridge live↔lab ; exploiter UI |
| **P4** | Claude Reviewer / Auditor / Research (rôles) | Copilot **EXISTE** ; Reviewer **ABSENT** | Reviewer d’abord |
| **P5** | Lab auto, Monte Carlo, comparaisons systématiques | Lab partiel | Après mesure stable |

---

## Première tranche recommandée — **T0 + T1**

### Pourquoi celle-ci ?

Le repo a déjà Lab + Evidence + Paper + Copilot.  
Le trou bloquant pour « Validation Desk » : **contrat de décision unique** + **review Claude mesurable** (sans remplacer le quant).

### T0 — DecisionSnapshot & versioning (engine)

**Done when :**

1. Type/DTO `DecisionSnapshot` (ou alias documenté de `SignalContext` enrichi) sérialisé.  
2. Champ `strategy_version` stable sur snapshot + evidence/decision persistée.  
3. `reason_codes` + conflicts list exposés (même partiels).  
4. Tests unitaires ; pas de nouvelle table si les colonnes JSON suffisent.  
5. Doc courte dans `EVIDENCE-ARCHITECTURE.md` (lien).

**Hors scope T0 :** nouveaux indicateurs, UI desk, Monte Carlo.

### T1 — ClaudeReviewer minimal (server + branchement)

**Done when :**

1. Endpoint ou mode dédié (ex. `POST /api/agent/review`) réutilisant Anthropic tool path.  
2. Schema `ClaudeReview` validé (Zod server + miroir Pydantic optionnel) — refus si invalide.  
3. Tools : snapshot / candidate / risk / performance **déjà calculés** (Python).  
4. Persist : `quant_decision`, `claude_review`, `final_paper_action`.  
5. Branche A/B paper (même signal_id) — même si UI = flag debug.  
6. Tests : JSON invalide → no paper ; mock Anthropic.  
7. Screener 100 marchés **sans** Claude ; Claude seulement sur N candidates filtrés.

**Hors scope T1 :** 5 agents séparés, Researcher auto-deploy, broker réel, MCP obligatoire, Grok.

---

## Tranche expérimentale T-EXP — PPO + BEST Cloud (Lab / shadow, **lots 1–3 livrés 2026-09-20**)

Objectif : savoir **par la mesure** si PPO (priorité haute) et BEST Cloud ALL MA
(priorité secondaire) apportent de l'information indépendante à
Ichimoku × RVOL × Structure. Ce ne sont **pas** des signaux BUY/SELL.

**Garde-fous (testés)** : aucun changement dans `decision/pipeline.py`,
`decision/combiner.py`, screener, paper, `evidence/context.py`, `agent_channel`.
Le ClaudeReviewer ne reçoit **pas** ces features (sinon sa review les utiliserait
et l'A/B de T1 ne mesurerait plus le quant seul). Un test garde-fou échoue si un
de ces chemins importe `ppo` / `best_cloud`.

| Lot | Contenu | Fichiers |
|-----|---------|----------|
| 1 | `PPO` 12/26/9 (EMA SMA-seedée), `PpoState` : histogramme, croisements signal/zéro, âges, `momentum` 5 niveaux sans seuil arbitraire | `engine/app/indicators/ppo.py` |
| 2 | `BestCloudState` : cloud entre 2 MA (EMA/SMA seulement), tendance, cross, distance % | `engine/app/indicators/best_cloud.py` |
| 3 | Branchement Lab : `FeatureBar`/`FeatureSeries`, clés de ruleset, évaluateur, rulesets `IV_EXP_*`, échelle `PPO_ABLATION_LAYERS`, mode `leave_one_layer_out` | `engine/app/strategy_lab/{features,ruleset,evaluator,catalog,ablation}.py` |

**Paramètres figés a priori** (ne pas optimiser sur la fenêtre d'ablation) :
PPO 12/26/9 ; BEST Cloud EMA 20 / EMA 50 (les défauts du script TradingView
n'ont pas été vérifiés). Toute variante = nouvelle hypothèse à déclarer avant
de regarder les résultats (multiple testing).

**Protocole d'ablation** (fenêtre OHLCV identique, bougies clôturées) :

```python
from app.strategy_lab.ablation import run_ablation_on_candles, PPO_ABLATION_LAYERS
# Modèles A→D : A_ICHIMOKU+B_RVOL | +C_BOS | +D_PPO | +E_BEST_CLOUD
run_ablation_on_candles(candles, symbol=..., timeframe="1h",
                        mode="cumulative", layers=PPO_ABLATION_LAYERS)
# Retirer une couche à la fois (FULL vs NO_D_PPO, NO_E_BEST_CLOUD, ...)
run_ablation_on_candles(candles, symbol=..., timeframe="1h",
                        mode="leave_one_layer_out", layers=PPO_ABLATION_LAYERS)
```

**Décision** : PPO/BEST Cloud n'entrent dans la Confluence (T5) que si le gain
(expectancy / PF / faux positifs, MFE/MAE) survit au walk-forward existant,
avec un N effectif suffisant (les signaux d'une même tendance se chevauchent).
Si retirer BEST Cloud ne change quasiment rien → redondant avec Ichimoku, écarté.

**Reste à faire (hors T-EXP actuel)** :

- Enregistrement live en shadow : bloc optionnel `experimental` de `SignalContext`
  (`context_json`, sans migration ; vérifier `evidence/matching.py` avant tout bump
  de `FEATURE_VERSION`). Dépend de T0.
- Test MTF (4H régime / 1H signal) : `FeatureBar` est mono-timeframe ; nécessite le
  bridge live↔lab (T3).
- Matrice de redondance (corrélation booléenne BEST Cloud vs Ichimoku, PPO vs RSI /
  `kijun_slope`) exécutée sur données réelles.
- Exposer PPO/BEST Cloud au ClaudeReviewer : seulement après verdict d'ablation.

---

## Tranches suivantes (ordre)

### T2 — Shadow mode produit

Enregistrer TradeCandidate sans fill ; OutcomeEngine (réutiliser `evidence/outcomes`) attache MFE/MAE / TP-SL hit.  
Séparer clairement des fills PaperBroker.

### T3 — Bridge FeatureBar live ↔ strategy_lab

Un chemin bar causal partagé ; tests d’écart.  
Puis ablation OBV/VWAP keys si manquantes dans ruleset.

### T4 — UI Strategy Lab

Rename `/app/backtests` → Strategy Lab (onglets Compare / Regimes / Experiments).  
Chiffres **uniquement** depuis DB.

### T5 — Confluence familles versionnées

Config poids TREND/STRUCTURE/PARTICIPATION/… versionnée + backtestable.  
Pas de poids magiques hardcodés en prod.

### T6 — Claude Auditor (+ plus tard Researcher)

Post-outcome `AuditReport` ; hypothèses → Experiment → Python backtest → human review.  
Jamais « Claude change la strat en prod ».

### T7 — Monte Carlo / Risk of ruin

Quand N trades suffisant.

---

## Anti-patterns (bloquer en review)

| Anti-pattern | Remplacer par |
|--------------|---------------|
| 5 agents Claude × tous les symboles | Screener Python → N candidates → 1 review |
| Claude calcule RSI/PF | Tools + Python |
| Remplacer quant_decision | Stocker les deux + A/B |
| Copier Pine AlgoPro / GrokBot | Concepts only |
| Ajouter JMA/SAR/MACD | Ablation d’abord sur briques existantes |
| UI « +1.77 ETH » inventé | Metrics DB only |
| Optimizer → prod sans OOS | Walk-forward Lab existant |

---

## Critère « feature terminée »

Pas : « la page affiche BUY ».

Oui : on peut répondre

- pourquoi BUY  
- données / bougie / version  
- conflits / risque / SL / TP  
- outcome (frais) / MFE / MAE  
- OOS / régime si claim de robustesse  

---

## Assignation indicative

| Tranche | Lead |
|---------|------|
| T0 | Claude Code (engine) |
| T1 | Cursor (server agent) + Claude Code (tools engine si besoin) |
| T2–T3 | Claude Code |
| T4 | Cursor |
| T5–T7 | selon charge, après T0–T3 verts |
