# Handoff — session Cursor (2026-09-16)

> **Pour :** Claude (engine) + prochaine session Cursor (front)  
> **De :** Cursor  
> **Suite de :** [`HANDOFF-CURSOR-PIPELINE-NATIVE.md`](./HANDOFF-CURSOR-PIPELINE-NATIVE.md) (§7–§11), Location V1.5, univers multi-marchés  
> **Ports :** Vite `5173` → Express `8787` → engine `8000`

---

## 1. Décisions produit (inchangées)

| Sujet | Statut |
|---|---|
| **Option A** badge/table = combiner legacy ; sheet = pipeline natif | **Confirmé** |
| **Option C** (combiner → portes) | **Non justifiée** (Sharpe PIPELINE &lt; Ichimoku seul ; Location baisse expo/DD, pas l’edge) |
| Location V1.5 | Livrée moteur ; front = même contrat `NativePipelinePayload` |
| Seuils RVOL/ATR | Settings → query params (voir §3 — **ne pas toujours les envoyer**) |

---

## 2. Ce que Cursor a livré (front / Express)

### Pipeline & backtests
- **Backtests** : 4 colonnes dont `PIPELINE` (« Pipeline (portes) ») ; seuils Settings relayés via `backtest.ts`.
- Sheet Décisions : pipeline natif + verdict portes ; Location affiche de vraies valeurs dès que le moteur les envoie.

### Univers multi-marchés (aligné Marché)
Même pattern d’onglets `market-class-tabs` + `GET /api/engine/universe` :

| Page | Comportement |
|---|---|
| **Marché** | Déjà multi-classe (crypto Binance / FX·métaux·indices Biquote / equity Twelve Data) |
| **Backtests** | Plus de `WATCHLIST` crypto-only → instruments **câblés** par classe |
| **Décisions** | Onglets classe ; filtre le cache screener ; **equity** = lignes locales + **détail au clic** (pas de scan masse Twelve Data) |

Fichiers : `BacktestsPage.tsx`, `DecisionsPage.tsx`, `MarketPage.tsx`, `lib/universe.ts`.

### CoinGecko 429 (Contexte aperçu)
- `marketContext.ts` : cache TTL **5 min** + dédup inflight + stale-on-429.
- `ContextPanel` : chargements indépendants (F&G survit si CG tombe).

### Screener timeout (« The operation was aborted due to timeout »)
**Cause :** `appendEngineThresholds` envoyait **toujours** les 7 seuils → moteur `has_overrides` → **bypass cache** → scan live watchlist (souvent **>45s**) → `AbortSignal.timeout` Express.

**Fix front :** n’envoyer les query params **que s’ils diffèrent des défauts** (`engineThresholds.ts`).  
**Fix Express :** timeout screener **120s**, autres **60s** ; message `engine_timeout` plus clair (`server/src/engine/proxy.ts`).

Mesure : screener **sans** overrides → 200 immédiat ; **avec** overrides défauts → timeout >50s.

### UX « aucune donnée » / latence hors crypto
- Claude a confirmé : redémarrages `--reload` en rafale (édits parallèles Cursor↔Claude) + décisions EURUSD/AAPL **3–19s** sans message clair = impression de vide.
- Front Décisions : ligne « Chargement du screener… » ; détail hors Binance : **« peut prendre 5–20s »**.

---

## 3. Pièges à ne pas re-introduire

1. **Ne jamais renvoyer les seuils RVOL/ATR par défaut** sur `/screener` — ça tue le cache.
2. **Ne pas scanner Twelve Data en parallèle** (equity) — détail / backtest **un symbole à la fois**.
3. **Biquote** ~100 barres/appel → accumulateur moteur (`app/market_data/accumulator.py`) ; historique long = lent au premier run.
4. Éviter d’éditer les mêmes fichiers engine **en parallèle** avec Claude pendant `uvicorn --reload`.
5. Express = **`:8787`**, pas `:3000`.

---

## 4. Stack runtime

```
Vite 5173  →  Express 8787 (/api/engine/*)  →  Python engine 8000
```

Santé attendue : `GET :8000/api/engine/health`, `/universe`, `/screener`, `/decisions/BTCUSDT|EURUSD|AAPL`.

---

## 5. Backlog front (CDC §11 — pour Cursor)

Rien ne bloque côté moteur pour ces items :

| Item | Travail |
|---|---|
| Stabiliser pipeline natif + labels FR partout | Audit UI encore « combiner-only » ; `decisionLabels.ts` |
| Price Action + MTF + ATR visibles | Sheet : structure HH/HL/BOS, MTF, régime ATR / stop (pas seulement codes bruts) |
| Persist / journal « confirm » utilisateur | Produit + Prisma `server/` (pas la DB engine) |

Optionnel plus tard : seuils Location en Settings (moteur ne les expose pas encore en query).

---

## 6. Backlog moteur (pour Claude — pas urgent)

- Seuils Location (lookback VP, VWAP, HVN/LVN) en query params si on veut calibrer comme RVOL/ATR.
- Perf décisions non-crypto (cache / accumulateur déjà là — mesurer après warm-up).
- Ne pas migrer Option C tant que Sharpe PIPELINE ne bat pas Ichimoku après recalibrage **honête** (autre fenêtre / pas overfit).

---

## 7. Fichiers front / proxy touchés récemment

```
ichivol-app/src/lib/engineThresholds.ts      — append conditionnel + hasCustomEngineThresholds
ichivol-app/src/lib/marketContext.ts         — cache CoinGecko
ichivol-app/src/lib/backtest.ts              — ExperimentName PIPELINE
ichivol-app/src/pages/BacktestsPage.tsx      — univers multi-classe + PIPELINE
ichivol-app/src/pages/DecisionsPage.tsx      — onglets classe + loading lent
ichivol-app/src/pages/MarketPage.tsx         — (réf. pattern univers)
ichivol-app/src/components/ContextPanel.tsx  — Promise.allSettled
ichivol-app/server/src/engine/proxy.ts       — timeouts 120s/60s
```

Engine (Claude / session parallèle, à connaître) :

```
app/indicators/location.py
app/market_data/biquote.py
app/market_data/accumulator.py
app/universe/catalog.py
app/market_data/resolve.py
```

---

## 8. Prochaine action recommandée

1. **Utilisateur :** Ctrl+F5, smoke Décisions (Crypto + Forex EURUSD) + Backtests multi-classe.  
2. **Cursor (si on enchaîne) :** ~~item CDC « Price Action + MTF + ATR visibles »~~ **fait 2026-09-16** (`DecisionPipelinePanel` + labels Location). Suite : journal « confirm » Prisma / polish labels FR restants.  
3. **Claude :** seulement si perf hors-crypto ou seuils Location — sinon laisser le front digérer le CDC §11.
