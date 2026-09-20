# ICHIVOL V2 — Audit (code = source de vérité)

**Date :** 2026-09-20  
**Handoff maître :** [`HANDOFF-CLAUDE-ALGOPRO-STRATEGY-LAB-2026-09-20.md`](./HANDOFF-CLAUDE-ALGOPRO-STRATEGY-LAB-2026-09-20.md)  
**Roadmap :** [`ICHIVOL_V2_ROADMAP.md`](./ICHIVOL_V2_ROADMAP.md)

Légende : **EXISTE** · **PARTIEL** · **ABSENT** · **À CORRIGER** · **À RÉUTILISER**

---

## 1. Architecture globale

| Zone | Paths | Statut |
|------|-------|--------|
| Backend Express / auth / agent | `ichivol-app/server/` | **EXISTE** |
| Engine FastAPI | `ichivol-app/engine/` | **EXISTE** |
| Frontend React/Vite | `ichivol-app/src/` | **EXISTE** |
| Compose / VPS | `docker-compose.yml`, `deploy/vps/` | **EXISTE** |
| Prisma (app DB) | `server/prisma/` | **EXISTE** |
| SQLAlchemy + Alembic (engine DB) | `engine/app/db/`, `engine/alembic/` | **EXISTE** |

---

## 2. Market Data & qualité

| Fonctionnalité | Statut | Notes |
|----------------|--------|-------|
| `MarketDataProvider` / registry | **EXISTE** | Abstrait ; Binance Vision câblé |
| Univers multi-classes | **PARTIEL** | Catalog ; non-crypto souvent `provider=None` |
| `volume_type` metadata | **EXISTE** | `volume_semantics.py` |
| Data validator / quality | **PARTIEL** | `market_data/quality.py` (closed bars, incomplete) — pas encore un gate « bad data → no BUY » exhaustif |
| Closed candles for decisions | **EXISTE** | `decide_on_closed_candles=True` ; screener `_closed_only` |
| Live price vs signal price | **EXISTE** | Live = last trade ; signal = closed series |
| Timezone / gaps / duplicates | **PARTIEL** | À durcir (tests qualité présents, couverture à étendre) |

**À RÉUTILISER :** `closed_candles()`, `VolumeType`, registry providers.  
**À CORRIGER :** tout chemin décision qui contournerait `_closed_only` (auditer paper auto / research_lab vs live).

---

## 3. Indicateurs & structure

| Brique | Statut | Path typique |
|--------|--------|--------------|
| Ichimoku 9/26/52/26 | **EXISTE** | `indicators/ichimoku.py`, analytics |
| RVOL | **EXISTE** | `indicators/rvol.py` |
| ATR | **EXISTE** | `indicators/atr.py` |
| ADX / régime | **EXISTE** | `adx.py` + stages pipeline |
| RSI | **EXISTE** | `rsi.py` |
| OBV / CMF | **EXISTE** | `obv.py`, `cmf.py` |
| VWAP / location | **EXISTE** | `location.py` (pertinence TF/marché à documenter) |
| Market Structure / BOS | **EXISTE** | `structure/`, adapters MVPP/trendln/pytrendline |
| S/R force / touches / volume niveau | **PARTIEL** | Structure présente ; enrichissement « force du niveau » à évaluer vs libs |
| Fib (contexte, pas géométrie MS) | **EXISTE** | `fibonacci/` (profils optionnels) |
| JMA / SAR / MAC-Z / Range Filter | **ABSENT** | **Ne pas ajouter** (étude AlgoPro) |

---

## 4. Signal / Decision / Confluence / Risk / MTF

| Fonctionnalité | Statut | Notes |
|----------------|--------|-------|
| Screener / pipeline décisions | **EXISTE** | `screener/service.py`, pipeline stages |
| Labels BUY/SELL/WATCH/NO_TRADE | **EXISTE** | |
| Multi-timeframe | **PARTIEL** | HTF dans screener ; pas encore `MarketContext/SignalContext/ExecutionContext` nommés produit |
| Confluence familles + poids versionnés | **PARTIEL** | Codes confluence + evidence ; pas de pondération produit versionnée type TREND 30%… |
| Reason codes stockés | **PARTIEL** | Evidence / pipeline codes ; journal explicabilité incomplet vs cible |
| Risk engine (SL/TP/sizing/RR) | **PARTIEL** | Paper gates + ATR SL/TP Lab ; pas un Risk Engine produit unique |
| `strategy_version` obligatoire | **PARTIEL** | Profiles / Lab / paper codes — à unifier sur DecisionRecord |
| Lookahead tests | **PARTIEL** | Doctrine + research closed-candle ; suite anti-lookahead à étendre |

---

## 5. Evidence, outcomes, performance

| Fonctionnalité | Statut | Path |
|----------------|--------|------|
| SignalContext (snapshot t0) | **EXISTE** | `evidence/context.py` |
| DecisionSnapshot nommé unifié | **PARTIEL** | Alias / DTO manquant |
| EvidenceEngine matching | **EXISTE** | `evidence/engine.py` |
| OutcomeTracker MFE/MAE / forward | **EXISTE** | `evidence/outcomes.py` (horizons bar) |
| Libellés T+1H clock | **PARTIEL** | Dérivable du TF |
| Performance metrics PF/Sharpe/… | **EXISTE** | `backtest/metrics.py`, Lab, Paper |
| Buckets RVOL / régimes / asset | **PARTIEL** | Regime slices Lab ; buckets RVOL produit incomplets |
| Monte Carlo | **ABSENT** | P5 |

---

## 6. Strategy Lab / backtest / ablation / WF

| Fonctionnalité | Statut |
|----------------|--------|
| Event study | **EXISTE** |
| Ruleset déclaratif `IV_*` | **EXISTE** |
| Ruleset backtest ATR | **EXISTE** |
| Perf DB experiments | **EXISTE** |
| Ablation | **EXISTE** |
| Regime slices | **EXISTE** |
| Walk-forward + opt | **EXISTE** |
| Même kernel live ↔ lab | **PARTIEL** / **À CORRIGER** (3 stacks : pipeline, strategy_lab, research_lab) |
| UI Strategy Lab | **PARTIEL** (`/app/backtests`) |

**À RÉUTILISER :** tout `strategy_lab/*` — ne pas réécrire.

---

## 7. Paper / shadow / journal

| Fonctionnalité | Statut |
|----------------|--------|
| PaperAccount / positions / orders | **EXISTE** (modèles + API) |
| Auto watchlist + user_confirmed | **EXISTE** |
| Fees / ledger (récent) | **PARTIEL** (brokerage en cours) |
| ShadowBroker counterfactual | **PARTIEL** |
| Shadow mode « signal only → outcome later » | **PARTIEL** (evidence outcomes ≈ ; pas produit unifié) |
| Decision journal rejouable | **PARTIEL** (Activity + evidence + decisions tables) |
| Séparation backtest ≠ paper | **EXISTE** conceptuellement — **À CORRIGER** si UI/confond |

---

## 8. Claude / agents

| Fonctionnalité | Statut |
|----------------|--------|
| Copilot chat Anthropic tool-use | **EXISTE** |
| OpenRouter/OpenAI fallback | **EXISTE** |
| Claude Agent SDK / MCP runtime | **ABSENT** (et non requis pour T1) |
| Grok / xAI | **ABSENT** — **ne pas ajouter** |
| ClaudeReviewer post-quant | **ABSENT** |
| Structured ClaudeReview schema | **ABSENT** |
| A/B quant vs quant+Claude | **ABSENT** |
| Auditor / Researcher rôles | **ABSENT** (chat peut improviser ; pas de pipeline) |
| Tools quant complets pour review | **PARTIEL** (agent_channel read-only large ; manque package « TradeCandidate ») |

**À RÉUTILISER :** `claudeAgent.ts`, `claudeTools.ts`, `agent_channel`, allowlist read-only.

---

## 9. Frontend pages (utile vs cible)

| Page | Statut vs cible |
|------|-----------------|
| Décisions + Evidence card | **À RÉUTILISER** |
| Synthèse / Paper / Activité | **À RÉUTILISER** |
| Backtests (= Lab de facto) | **À RÉUTILISER** → rename Strategy Lab |
| Copilot `/app/agent` | **À RÉUTILISER** → brancher Reviewer à part |
| AI Trading Desk dashboard | **ABSENT** (ne pas fake P&L) |

---

## 10. Bugs / risques / dette

| Item | Type |
|------|------|
| Triple stack backtest/live/research | **Dette** — divergence silencieuse |
| Confiance combiner MVP vs evidence rate | **Risque produit** — ne pas présenter comme proba |
| Tokens Claude × screener large | **Risque coût** — filter Python d’abord |
| Working tree moteur « sale » + deploy web | **Risque ops** (handoff deploy) |
| Overfitting si optimizer avant bridge live/lab | **Risque scientifique** |
| Source AlgoPro non officielle | **Risque légal/éthique** — concepts only |

---

## 11. Ne pas toucher / réutiliser / ajouter

### Ne pas toucher

- North star 5 questions  
- Glossaire Paper vs Shadow  
- Closed-candle default  
- Volume semantics  
- Confirmations write agent  

### Réutiliser

- `strategy_lab`, `evidence`, paper profiles, screener pipeline, Claude tool loop, Structure adapters, metrics  

### Ajouter (par priorité roadmap)

1. DecisionSnapshot + strategy_version durci  
2. ClaudeReviewer + schema + A/B storage  
3. Bridge features live↔lab  
4. UI Lab / Desk **sans** chiffres inventés  
5. Monte Carlo / Research agent **plus tard**

---

## 12. Inspirations externes (statut)

| Source | Usage autorisé |
|--------|----------------|
| AlgoPro / TraderOracle Pine | Concepts confluence — **pas** de code |
| GrokBot Trading Desk prompt | Patterns desk multi-rôle — **pas** Grok API |
| trend-line-detector / trendln / pytrendline | Déjà / comparer avant d’étendre |
