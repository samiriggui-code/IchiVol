# Upgrades IchiVol depuis les 4 repos JEV (hors QuantDinger)

> QuantDinger a son audit dédié : [`EVE-QUANTDINGER-AUDIT-2026-10-16.md`](./EVE-QUANTDINGER-AUDIT-2026-10-16.md)  
> (gate 5 CHOICE, Event Radar, Settings schema — **ne pas re-prioriser ici**)

---

## Vue par repo

### 1. `feder-cr/jev` (jevos-v4) — runtime déjà sur VPS

| Récupérer | Cible IchiVol | Prio |
|---|---|---|
| Fingerprint SHA modèle dans `/health` | Persister dans dossier / `jev_json` | P1 |
| Pin `response_model` vs `JEV_MODEL` (anti silent-upgrade) | `adapter.py` | P1 |
| Erreurs wire structurées | `normalize.py` | P2 |
| Server-Timing (ops) | history / panel | P3 |

**Pas :** sources C++ / OpenVINO / binaire — on reste client HTTP.

---

### 2. `jarrodwatts/jev-trader` — dry-run + latence

| Récupérer | Cible IchiVol | Prio |
|---|---|---|
| **Late / timeout → HOLD** (jamais trade sur état périmé) | `orchestrator` + timeout adapter | **P0** |
| Mock / stand-in **labellisé** si JEV down | badge panel + `source: heuristic` | P1 |
| Latence + coût Jev visibles | EveIntelligencePanel | P2 |
| SSE stream décisions | optionnel UI | P3 |

**Pas :** Monad, wallets, Kuru, gas, market-making live.

---

### 3. `buberlo/jev-trader` — le plus riche pour Ève

| Récupérer | Cible IchiVol | Prio |
|---|---|---|
| **Fallback ladder** (conf / late / JEV down / kill) | `orchestrator` + `modes` | **P0** |
| Batterie 6 jugements atomiques (adaptée IchiVol) | Guardian / pré-paper (complément QD) | P1 |
| `HeuristicJudge` déterministe | fallback quand adapter `ok:false` | P1 |
| Triples + **probs au decision_time** | `dossier.decision_time_json` | P1 |
| `low_confidence_scale` | `paper_submit` + policy thresholds | P1 |
| Brier / ECE / reliability (**observe-only**) | `eve/calibration.py` | P2 |
| Snapshot dense &lt;400 tokens | `eve/context.py` | P2 |
| Precedence risk KILL&gt;HOLD&gt;REDUCE | aligner docs Guardian ↔ Risk Kernel | P2 |

**Pas :** Avellaneda-Stoikov, quote cancel/replace, Kelly live, auto-Platt, kill Eve propriétaire.

---

### 4. `Gamma-Software/jev-signals-lab` — règles en code

| Récupérer | Cible IchiVol | Prio |
|---|---|---|
| 12 questions → **`strategy()` AND gates en code** | `eve/signal_rules.py` + Analyst | P1 |
| Signaux portables : event_risk, overextended, momentum, technical_setup | questions modes | P1 |
| Offline demo labellisé | même contrat fallback | P2 |
| Tests unitaires des règles | `tests/eve/test_signal_rules.py` | P2 |
| Affichage raw signals + rule string | panel | P3 |

**Pas :** Express Node, questions equities brutes non adaptées, broker.

---

## Top 10 upgrades (tous repos hors doublons QD)

| # | Upgrade | Repos | Où brancher |
|---|---|---|---|
| 1 | Fallback ladder + late→HOLD | buberlo + jarrodwatts | `orchestrator.py` |
| 2 | Timeout JEV → jamais LONG/SHORT | jarrodwatts | `adapter` + synthèse |
| 3 | Persister probs JEV au decision_time | buberlo | `dossier.py` |
| 4 | Batterie atomiques + règles code (modes) | Gamma + buberlo | `modes` / `signal_rules` *(gate 5 CHOICE = QD)* |
| 5 | Heuristic / offline-demo labellisé | buberlo + Gamma + jarrodwatts | panel + orchestrator |
| 6 | low_confidence → reduce/abstain paper | buberlo | `paper_submit` |
| 7 | Fingerprint + pin modèle | feder-cr | `adapter.health` |
| 8 | Brier/ECE observe-only | buberlo | `calibration.py` |
| 9 | Context dense budget tokens | buberlo + jarrodwatts | `context.py` |
| 10 | SSE follow-up (optionnel) | jarrodwatts | UI |

---

## Déjà fait (ne pas refaire)

- Adapter jevos/TypeSafe, 4 modes, paper dry-run flag off, follow-up J/K, calib observe, timeline dossier UI  
- Audit QuantDinger : gate / radar / settings schema  

### Appliqué 2026-10-16 (session locale — P0/P1)

| Item | Fichiers |
|---|---|
| Fallback ladder late→HOLD / low_conf→ABSTAIN / jev_down labellisé | `eve/degradation.py`, `eve/heuristic.py`, `orchestrator.py` |
| Timeout adapter → `late: true` + fingerprint health + model_mismatch | `jev/adapter.py` |
| Probs JEV + fingerprint + degradation dans `decision_time` | `orchestrator.py` |
| Paper execute forcé off si dégradé | `eve/paper_submit.py` |
| Seuils `min_jev_confidence` | `eve/calibration.py` |
| Badge dégradation UI | `EveIntelligencePanel.tsx` |
| Tests | `tests/eve/test_degradation.py` |
| Settings schema knobs JEV/Radar (QD P0) | `eve/settings_schema.py`, `SettingsPage` Ève/JEV, `config.py` |
| Signal rules AND (Gamma) | `eve/signal_rules.py` + orchestrator → ABSTAIN |
| Context dense &lt;400 tokens (buberlo) | `eve/context.dense_jev_state` / `jev_state_for` → modes + entry_gate |

---

## Ne jamais importer

Live brokers · wallets · MM A-S · portefeuille Eve · fail-open live · auto-apply Platt · OpenRouter comme System One · billing SaaS
