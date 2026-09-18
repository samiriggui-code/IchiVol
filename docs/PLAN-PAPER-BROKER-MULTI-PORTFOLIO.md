# Plan — Paper Broker + validation multi-signaux

**Status:** Phase 1 **déployée VPS** (2026-09-18) — PaperBroker live  
**Date:** 2026-09-18  
**Scope:** engine paper layer only · no real orders · freeze baseline · unlock multi-portfolio  
**Architecture lab :** [`ARCHITECTURE-CONSOLIDEE-V2.md`](./ARCHITECTURE-CONSOLIDEE-V2.md)  
**Analyse structure (pré-Phase 2) :** [`ANALYSE-STRUCTURE-ENGINES.md`](./ANALYSE-STRUCTURE-ENGINES.md)

---

## Verdict

Ne pas optimiser le pipeline sur les 31 trades (−3,8 %).  
**PaperBroker** capitalisé (5 000 €) + freeze **`ICHIVOL_BASELINE_V1`** sont en place sur le VPS.  
Prochaine étape produit : laisser tourner quelques cycles, puis **Phase 2 Market Structure** (voir archi consolidée). Les modules structure / régime / Fib **gagnent leur place** via expectancy / drawdown hors échantillon — sinon on les retire.

---

## État actuel (constat)

| Élément | Aujourd’hui |
|--------|-------------|
| Paper | SQLAlchemy `PaperPosition` (engine DB) — pas de Prisma |
| Ouverture | `BUY`/`SELL` pipeline → qty=1 implicite, PnL en `%` |
| Sortie | flip / downgrade pipeline (ou manuel) — **pas de stop/TP exécuté** |
| Coûts | backtest seulement (`commission_bps` / `slippage_bps`) |
| Expectancy | existe (mean `pnl_pct`) — **pas d’equity curve / max DD capital** |
| ATR | déjà dans le pipeline + `suggested_stop_distance` — **non branché sur le sizing paper** |
| RSI / CMF / Fib / VWAP | quasi absents en code |

Sources clés : `engine/app/paper/engine.py`, `performance.py`, `screener/cache.py`, `backtest/evidence.py`, digest `server/src/notifications/digest.ts`.

---

## Architecture cible (compatible multi-portfolio dès Phase 1)

```text
MARKET / SCREENER CACHE
        ↓
FEATURE + PIPELINE (inchangé pour baseline)
        ↓
STRATEGY PROFILE (ICHIVOL_BASELINE_V1 | A…G)
        ↓
RISK ENGINE (sizing, caps)
        ↓
PAPER BROKER (fills, cash, stops/TP, fees)     ← 5 000 €
        ↓
JOURNAL + EQUITY SNAPSHOTS
        ↓
PERFORMANCE (expectancy €, PF, max DD, MFE/MAE)

NO_TRADE / filtres rejetés  →  SHADOW BROKER (counterfactual, hors cash)  [Phase 5]
```

**Règle :** aucun indicateur n’ouvre une position.  
`indicateurs → observations → (profil) → risque → PaperBroker`.  
**ShadowBroker ≠ PaperBroker** — voir glossaire dans [`ARCHITECTURE-CONSOLIDEE-V2.md`](./ARCHITECTURE-CONSOLIDEE-V2.md).

### Tables (engine)

1. **`paper_portfolios`** — `code`, cash, equity, `strategy_profile` JSON figé, `initial_cash_eur=5000`
2. **`paper_orders`** — fills virtuels (prix demandé / fill, qty, fees, spread/slippage bps)
3. **`paper_equity_snapshots`** — cash, mark-to-market, equity, drawdown (pour max DD réel)
4. **`paper_journal_events`** — append-only (OPENED / CLOSED / STOP_HIT / … + payload JSON)
5. **Étendre `paper_positions`** — `portfolio_id`, qty, notional, stop/TP, fees, `entry_signal` JSON, PnL €, MFE/MAE, high/low seen

Unique open : `(portfolio_id, symbol, timeframe)`.

### Modules (nouveaux / étendus)

| Module | Rôle |
|--------|------|
| `paper/strategy_profiles.py` | profils figés (baseline + futurs A–G) |
| `paper/portfolio.py` | seed / lookup portefeuilles |
| `paper/risk.py` | risk % × equity / stop distance → qty |
| `paper/broker.py` | exécution virtuelle uniquement |
| `paper/mark_to_market.py` | MFE/MAE + snapshots equity |
| `paper/performance.py` | metrics capital (pas seulement % unitaire) |
| `paper/sync.py` | bridge screener → N portefeuilles |
| `paper/engine.py` | **compat** endpoints existants |

---

## Freeze `ICHIVOL_BASELINE_V1`

- Backfill `portfolio_id` sur les lignes paper existantes.
- Comportement d’entrée/sortie **identique** à aujourd’hui (pipeline BUY/SELL, exit flip/downgrade).
- Pas de changement de `decision/pipeline.py`, screener ranking, ou seuils “pour améliorer” le digest.
- Métriques capital **nouvelles** affichées **à côté** des métriques `%` historiques — ne pas fusionner les deux headlines.

---

## Décisions Phase 1 (validées 2026-09-18)

| Sujet | Choix figé |
|-------|------------|
| Capital | `5 000 EUR` / portefeuille |
| Crypto USDT | `USDT ≈ EUR` proxy, label explicite `valuation_mode=USDT_AS_EUR_PROXY` |
| Risk / trade | `1 %` equity (profils expérimentaux 0,25 / 0,50 possibles plus tard — **ne remplacent pas** le baseline) |
| Stop | `suggested_stop_distance` ATR ; **sans ATR → pas d’ouverture** (portefeuilles capitalisés) |
| TP | `2R` fixe (explicable, comparable) |
| Max open | `5` positions / portefeuille |
| Caps | max notional `25 %` equity / trade |
| Coûts | bps alignés backtest, stockés **par ordre** |
| Enforcement stop/TP | Phase 1 : mark sur prix screener ; suivi : high/low bougie |

---

## Phase 1 — premier milestone (PR unique)

**But :** broker + journal + metrics capital + freeze baseline. **Pas** encore A–G, Market Structure, Fib/RSI.

### Checklist

1. Modèles + migration Alembic (+ seed baseline + backfill)
2. `strategy_profiles.ICHIVOL_BASELINE_V1`
3. `risk.py` + `broker.py` + `mark_to_market.py`
4. Upgrade `performance.py` (equity, max DD, expectancy €, PF)
5. Routes `GET /paper/portfolios[...]` **sans casser** `/paper/positions|performance`
6. Screener cache : sync baseline inchangé ; hook prêt pour multi-portfolio
7. Tests unitaires sizing / fees / PnL / DD
8. Front `PaperPage` minimal : equity, cash, DD, stop/TP, MFE/MAE, PnL €
9. Digest V2 **léger** : section PaperBroker (capital / equity / DD / expectancy) — sans modules A–G

### Hors Phase 1

- Ordres réels / adapters broker / MCP MT5  
- Optimisation pour “réparer” −3,8 %  
- Market Structure / RSI / CMF / Fib comme gates  
- Portefeuilles A–G live  
- ShadowBroker counterfactual / walk-forward complets  
- tradingview-mcp (viz) — parallèle OK plus tard, pas bloquant  
- Dashboard multi-portfolio lourd  

---

## Phases suivantes (alignées Architecture consolidée V2)

| Phase | Contenu |
|-------|---------|
| **2** | Market Structure · adapters · StructureConsensus · Breakout / Retest · profils `STRUCTURE_*` / `ICHIVOL_MS_V1` · gate `block_near_opposing` · shadow journal `SHADOW_BLOCKED` — **livré** ; baseline non modifié |
| **3** | Context : ATR (déjà), Regime hard, RSI, CMF/OBV — **livré** (`indicators/rsi|cmf|obv`, `context/gate.py`, profils `ICHIVOL_CTX_*`) |
| **4** | FibonacciContext · multi-portfolio **A–G** · expériences `STRUCTURE_*` |
| **5** | ShadowBroker (counterfactual) · walk-forward / OOS |
| *∥* | tradingview-mcp = yeux / interaction — **pas** un indicateur |
| *plus tard* | MCP MT5 — après preuve Paper + Shadow |

Critère d’admission d’un module : **améliore expectancy et/ou max DD hors échantillon** vs `ICHIVOL_BASELINE_V1` — sinon retrait.

---

## Multi-portefeuille (pourquoi le pousser tôt)

Dès que le schéma `portfolio_id` existe, Phase 4 = **seed de 7 rows + 7 profiles**, pas une réécriture.  
Chaque cycle screener nourrit les N comptes avec le **même** timestamp / prix / pipeline — seule la règle de filtre/sizing/sortie change.

```text
PORTFOLIO A  Ichimoku seul
PORTFOLIO B  Ichimoku + RVOL                    = ICHIVOL_BASELINE_V1
PORTFOLIO C  IchiVol + ATR
PORTFOLIO D  IchiVol + Market Structure
PORTFOLIO E  IchiVol + Market Structure + Regime
PORTFOLIO F  IchiVol + Market Structure + Fibonacci
PORTFOLIO G  IchiVol Full
```

Expérience structure (Phase 4) : `STRUCTURE_MVPP` · `STRUCTURE_TRENDLN` · `STRUCTURE_PYTRENDLINE` · `STRUCTURE_CONSENSUS`.

---

## Risques

- Confusion métriques `%` legacy vs equity € → UI séparée  
- Confusion PaperBroker vs ShadowBroker vs « shadow portfolio » auto → glossaire archi consolidée  
- Corrélation crypto → max positions + notional cap obligatoires  
- Stop sur close screener seulement → biais court terme jusqu’au mark OHLC  
- FX USDT/EUR proxy → documenté, pas “vrai” FX  

---

## Go Phase 1 — fait (VPS 2026-09-18)

1. ~~Valider décisions Phase 1 (1 % risk, 2R, max 5, USDT≈EUR).~~ **Oui**  
2. ~~Autoriser Phase 1 only.~~ **Déployé** — faux compte `ICHIVOL_BASELINE_V1` 5 000 €, PaperPage, sizing ATR quand dispo  
3. **Avant Phase 2 :** laisser tourner ≥ quelques cycles screener ; hard-refresh Paper ; vérifier equity / cash / DD / nouveaux trades dimensionnés (anciens = historique `%` seulement)  
4. Reporter A–G / Structure / Fib / RSI / Shadow jusqu’à stabilisation métriques capital  

### Checklist smoke post-déploiement

- [ ] Hard-refresh `/app/paper` → bloc PaperBroker visible (cash, equity, drawdown)
- [ ] Portefeuille `ICHIVOL_BASELINE_V1` seeded à ~5 000 €
- [ ] Prochain trade auto avec ATR → qty / stop / TP / fees renseignés
- [ ] Trade sans ATR → pas d’ouverture capitalisée (ou legacy % selon règle codée)
- [ ] Aucun ordre réel (paper only)
- [ ] Digest / Overview ne confondent pas `%` legacy et equity €

Quand la checklist est OK → go Phase 2 (`ANALYSE-STRUCTURE-ENGINES.md`).
