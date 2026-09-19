# IchiVol × GPTHEIST — Architecture Lab (PHASE 0)

**Status:** audit complete — implement progressively, never replace Grand V2  
**Date:** 2026-09-19  
**Branch:** `cursor/gptheist-architecture-lab-a2fe`  
**North star:** [`TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md)  
**Evidence (unmerged sibling):** `origin/cursor/evidence-engine-consolidation-a2fe` → [`EVIDENCE-ARCHITECTURE.md`](./EVIDENCE-ARCHITECTURE.md)  
**Paper suggest→act (unmerged):** `origin/cursor/paper-suggest-act-a2fe`

> **DON'T TRUST A SIGNAL. MEASURE IT.**  
> IchiVol = market analysis lab — not a trading bot, not a wallet, not live execution.

---

## 1. ICHIVOL CURRENT ARCHITECTURE

```text
MarketDataProvider (Binance / BiQuote / Twelve Data)
        │
        ▼
scan_symbol (screener/service.py)
  ├─ ichimoku_agent + rvol_agent
  ├─ combiner.py          → STRONG_BUY…WAIT (MVP label, still API top-level)
  ├─ indicators.*         → structure / ATR / location / CVD / ADX / Donchian
  └─ build_pipeline()     → BUY|SELL|WATCH|NO_TRADE  (product gates)
        │
        ├─ persist_scan → Decision row (combiner fields today)
        ├─ paper sync_auto_watchlist (+ optional structure/fib/context gates)
        ├─ strategy_lab (event study / ablation / walk-forward / perf_db)
        └─ UI: DecisionsPage + DecisionPipelinePanel + PaperPage
```

**Product rule already encoded:** stages after Direction may only *downgrade* (WATCH / NO_TRADE). They never flip LONG↔SHORT.

---

## 2. EXISTING MODULES (inventory)

| Area | Path | Notes |
|------|------|-------|
| Direction agent | `engine/app/agents/ichimoku_agent.py` | Only voter |
| Participation agent | `engine/app/agents/rvol_agent.py` | Always NEUTRAL; confidence from RVOL |
| Pipeline gates | `engine/app/decision/pipeline.py` | Direction→Participation→Structure→Location→Regime |
| Combiner MVP | `engine/app/decision/combiner.py` | Do **not** promote as product truth |
| Live structure | `engine/app/indicators/structure.py` | HH/HL + BOS for live stage |
| Zone/TL structure | `engine/app/structure/*` | Consensus adapters (MVPP/trendln/pytrendline) — paper/API |
| Location | `engine/app/indicators/location.py` | VP + VWAP/AVWAP |
| Regime | ATR + ADX + Donchian in `_regime_stage` | Also `strategy_lab/regime.py` |
| Momentum (RSI) | `engine/app/indicators/rsi.py` | Paper/lab only today |
| Risk sizing | `engine/app/paper/risk.py` | Capital geometry, not direction |
| Paper / Shadow | `engine/app/paper/*`, `shadow/*` | Virtual only |
| Event study MFE/MAE | `engine/app/strategy_lab/event_study.py` | Forward path stats |
| Ablation | `engine/app/strategy_lab/ablation.py` | Cumulative + leave-one-out |
| Walk-forward | `engine/app/strategy_lab/walk_forward.py` | IS/OOS |
| Perf DB | `engine/app/strategy_lab/perf_db.py` | `ENGINE_VERSION = strategy_lab_v1` |
| Backtest experiments | `engine/app/backtest/experiments.py` | ICHIMOKU_ONLY / RVOL / PIPELINE |

---

## 3. EXISTING / PARTIAL / MISSING vs target stages

| Target stage | Status | Where |
|--------------|--------|-------|
| DATA QUALITY | **MISSING** | Fetch skip only |
| REGIME | **EXISTING** (order: last) | `_regime_stage` — target wants earlier |
| ICHIMOKU | **EXISTING** | agent + Direction stage |
| VOLUME | **EXISTING** | RVOL + Participation |
| STRUCTURE | **PARTIAL** | Live swings ≠ zone consensus |
| MOMENTUM | **PARTIAL** | RSI exists, not live stage |
| LOCATION | **EXISTING** | Location stage |
| RISK VETO | **PARTIAL** | Paper gates (`structure`/`fib`/`context`) + ATR fail; no dedicated live veto coordinator |
| DECISION | **EXISTING** (dual) | Pipeline + combiner |
| SNAPSHOT | **PARTIAL** | Persist combiner; pipeline stages not first-class on Decision row |
| HISTORICAL VALIDATION | **PARTIAL** | Event study + backtest evidence; similar-setup matcher on Evidence branch |
| PERFORMANCE DB | **EXISTING** | Lab experiments table |
| EXPERIMENT / ABLATION | **EXISTING** | Priority reuse — extend, don't rewrite |
| PAPER | **EXISTING** | Broker + portfolios |

---

## 4. GPTHEIST CONCEPTS TO REUSE

Research clone: `ichivol-app/research/gptheist/` (gitignored vendor).

| Concept | GPTHEIST source | IchiVol mapping |
|---------|-----------------|-----------------|
| Ownership per stage | `docs/AGENTS.md` | Each `StageId` owns one question |
| Immutable input + prior handoffs | `src/simulation.ts` | Candles ≤ T + prior `AnalysisStage` list |
| PASS / VETO / INFO outcomes | `AgentOutcome` | Extend `StageStatus` (+ `VETO` alias of hard fail) |
| Non-bypassable veto | PALERMO | Risk gate: cannot upgrade a veto |
| Final coordinator | PROFESSOR | Decision engine: synthesizes labels, never flips veto→PASS |
| Deterministic runId | sha256(policy+fixture) | `engine_version` + `market_data_hash` + config |
| Append-only audit | `runs/*.jsonl` | Engine audit JSONL / DB append |
| Fixture determinism tests | `tests/simulation.test.ts` | Same fixtures → same decision |
| Paper-only execution mode | `EXECUTION_MODE` | Already: never live |

### Do **not** copy

- City agent names (TOKYO…PROFESSOR)
- Memecoin / Pons / Robinhood Chain desk
- Demo thresholds as product policy
- LLM-as-decision-stage framing
- GPTHEIST as backtester (it isn’t one)

---

## 5. TREND REPOS CONCEPTS TO REUSE

Clones under `ichivol-app/research/` — **research only**. Runtime already has clean-room adapters.

| Repo | Already in IchiVol? | Absorb? |
|------|---------------------|---------|
| `trend-line-detector` (mvpp) | `structure/adapters/mvpp.py` | Keep primary; optional clean-room tweaks only. Leave bounce lookahead out (bias). |
| `trendln` | `structure/adapters/trendln.py` | Keep 2nd opinion geometry. Do **not** vendor findiff/Hough. |
| `pytrendline` | `structure/adapters/pytrendline.py` | Offline / opt-in only (`include_pytrendline`). |

**Verdict:** do not add research packages as production dependencies. Enrich `MarketStructure` via adapters + consensus.

---

## 6. MISSING COMPONENTS (priority)

1. **`AnalysisStage` contract** — serializable handoff object (this branch starts it)
2. **Data Quality stage** — gaps, duplicates, warmup, volume_type sanity
3. **Unified Risk Veto coordinator** — promote paper gate pattern to explicit live-optional stage
4. **Momentum as optional pipeline stage** — behind config / ablation flag
5. **Immutable Signal Snapshot** — pipeline + versions + data hash
6. **Append-only run audit** — GPTHEIST-style JSONL for replay
7. **Merge Evidence Engine branch** — similar-setup matching + volume_type
8. **Ablation UX / config switch** — “disable RVOL / Structure / Risk and re-run N years” as first-class API

---

## 7. PROPOSED TARGET ARCHITECTURE

```text
DATA QUALITY ──► REGIME ──► ICHIMOKU ──► VOLUME ──► STRUCTURE
      │                                              │
      │         (optional) MOMENTUM ◄────────────────┤
      │                                              ▼
      │                                         LOCATION
      │                                              │
      └──────────────► RISK VETO ◄───────────────────┘
                           │
                           ▼
                    DECISION ENGINE
                     (dimensions kept separate — no magic score)
                           │
                           ▼
                    SIGNAL SNAPSHOT
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Evidence DB   Event Study   Ablation / WF
              │            │            │
              └────────────┴────────────┘
                           ▼
                    PERFORMANCE DB
                           ▼
                    PAPER FORWARD (virtual)
```

**Principles**

- Deterministic Python stages; LLM only for explanation later.
- Keep dimensions separate (no 83/100 BUY score as product truth).
- Analysis signal ≠ strategy simulation (entry/stop/fees required before Sharpe/PF claims).
- Ablation answers: *which module adds value?*

---

## 8. MIGRATION PLAN (phased)

| Phase | Work | Risk |
|-------|------|------|
| **0** | This audit + research clones + doc | None |
| **1** | GPTHEIST concept map (done in this doc) | None |
| **2** | `AnalysisStage` contract + adapters from `PipelineStage` | Additive |
| **3** | Data Quality stage (optional fail-closed) | Low — opt-in first |
| **4** | Regime adapter (reuse `_regime_stage`; optional early order behind flag) | Medium if reorder live |
| **5–6** | Ichimoku / RVOL adapters (wrap existing agents) | Low |
| **7** | Structure: unify live swings + optional consensus handoff | Medium |
| **8** | Momentum stage (config-gated) | Low |
| **9** | Location adapter | Low |
| **10** | Risk Veto coordinator (Palermo pattern) | Medium — must not flip decisions |
| **11** | Decision engine synthesis (LONG_CANDIDATE… + factors) | Medium — dual labels |
| **12** | Audit / replay JSONL | Low |
| **13** | Historical validation (merge Evidence branch + event study) | Medium |
| **14** | Experiment / ablation first-class config | **Highest product value** |
| **15** | Paper forward alignment with snapshots | Low |
| **16** | UI: reasoning panel + historical context | Front only |

At each phase: tests + commit + no regression on `build_pipeline` defaults.

---

## 9. FILES TO CREATE

| File | Purpose |
|------|---------|
| `engine/app/analysis/stage.py` | `AnalysisStage` + status enum + JSON serialization |
| `engine/app/analysis/handoff.py` | Run bundle: stages + run_id + versions |
| `engine/app/analysis/adapters/pipeline.py` | Map `PipelineResult` → handoff (no behavior change) |
| `engine/app/analysis/audit.py` | Append-only JSONL writer (Phase 12) |
| `engine/tests/analysis/test_stage_contract.py` | Determinism / shape tests |
| `ichivol-app/research/README.md` | How to use research clones |
| This doc | Source of truth for the lab migration |

---

## 10. FILES TO MODIFY (later phases — not bulk rewrite)

| File | Change |
|------|--------|
| `decision/pipeline.py` | Optional export of AnalysisStage; keep `PipelineResult` API |
| `screener/service.py` | Attach handoff + data-quality; persist snapshot fields |
| `screener/persistence.py` | Store pipeline stages / run_id |
| `api/routes.py` | Expose handoff + experiment toggles |
| `strategy_lab/ablation.py` | Stage enable/disable config aligned with AnalysisStage ids |
| Front `DecisionPipelinePanel` | Show VETO / supporting / opposing factors |
| `.gitignore` | Ignore `ichivol-app/research/*` vendor trees |

---

## 11. TEST PLAN

| Suite | Asserts |
|-------|---------|
| Contract | Stage JSON round-trip; exhaustive status switch |
| Determinism | Same fixture + config + engine_version → identical handoff |
| Anti-lookahead | Stages only see candles ≤ T |
| Risk veto | Conflicting bullish stages + veto reason → NO_TRADE / INVALID; cannot upgrade |
| Ablation | ICHIMOKU_ONLY vs +RVOL vs +STRUCTURE vs +RISK deltas persisted |
| Replay | Audit JSONL reload equals live handoff |
| Regression | Existing `tests/` pipeline / paper / strategy_lab still green |

Fixtures to add under `engine/tests/analysis/fixtures/`: bullish, bearish, range, high_vol, bad_data, conflicting, risk_veto.

---

## 12. RISKS / REGRESSIONS

| Risk | Mitigation |
|------|------------|
| Dual decision labels (combiner vs pipeline) | UI already prefers pipeline; deprecate combiner gradually |
| Two Structure engines | Keep live swings for gate; consensus as optional enrichment / paper |
| Reordering REGIME early | Feature-flag; default = current order |
| Magic score temptation | Decision engine stores factor lists, not a single 0–100 product score |
| Overfitting via param grid | Walk-forward + experiment_id mandatory |
| Research deps in prod | Gitignore + adapters only |
| Unmerged Evidence / Paper branches | Rebase onto this lab after Phase 2; don't fork semantics |
| Live trading creep | Hard invariant: paper-only; no wallets; no real orders |

---

## 13. RESEARCH LAYOUT

```text
ichivol-app/research/
  README.md                 ← tracked
  gptheist/                 ← gitignored clone
  trend-line-detector/      ← gitignored
  trendln/                  ← gitignored
  pytrendline/              ← gitignored
```

Clone commands documented in `ichivol-app/research/README.md`.

---

## 14. IMMEDIATE NEXT IMPLEMENTATION (Phase 2)

1. Land `AnalysisStage` + pipeline adapter (additive).
2. Unit tests for serialization + determinism mapping.
3. Do **not** change live screener behavior yet.
4. Next: Data Quality (Phase 3) behind a flag.
5. Parallel track: merge Evidence Engine when ready for historical matching UI.

---

## Appendix — GPTHEIST → IchiVol name map

| GPTHEIST | IchiVol |
|----------|---------|
| TOKYO | Observe / Data frame |
| BERLIN | Lock criteria / thresholds |
| RIO | Direction (Ichimoku) |
| DENVER | Participation (RVOL) |
| LISBON | Evidence / handoff validate |
| STOCKHOLM | Location + sizing hints |
| NAIROBI | Structure / MTF brief |
| HELSINKI | Audit trace |
| PALERMO | Risk Veto |
| PROFESSOR | Decision coordinator (paper-only) |
