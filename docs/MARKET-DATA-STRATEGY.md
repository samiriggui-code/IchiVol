# IchiVol — Stratégie données marché (verrouillée)

**Statut : VERROUILLÉ** — 2026-09-15.  
Lié à : [`TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md) · [`APP-ARBORESCENCE-V2.md`](./APP-ARBORESCENCE-V2.md)

---

## 0. Règle primordiale

> **IchiVol n’est pas une plateforme Binance (ni Bybit, ni OKX).**  
> Les exchanges publics servent de **sources de données de marché**.  
> L’**exécution** (paper puis live) est un adaptateur **séparé**, branché plus tard, sur le venue que tu choisiras — ou aucun, si tu ne fais que signaler.

| Couche | Question | Exemple Phase 1 | Exemple plus tard |
|--------|----------|-----------------|-------------------|
| **MarketData** | D’où viennent OHLC / volume / OI ? | Binance public (klines), Bybit (OI/funding) | Autre feed, agrégateur payant |
| **Indicators** | Qui calcule Ichimoku, RVOL, ATR… ? | **Toujours ton Python** | Toujours ton Python |
| **Decision** | Quel label BUY/WATCH/NO_TRADE ? | Decision Engine IchiVol | Idem |
| **Execution** | Où passe l’ordre ? | PaperBroker (simulé) | Broker / CEX / DEX de ton choix |

**Ne jamais** confondre « on lit Binance Vision » avec « on trade chez Binance ».

### Preuve officielle Binance — Market Data Only

Binance documente des URLs **données de marché uniquement**, sans authentification, sans trading :

- Doc : [Market Data Only URLs](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md)
- REST : `https://data-api.binance.vision` — klines, trades, depth, tickers, exchangeInfo, etc.
- WebSocket : `wss://data-stream.binance.vision` — streams marché publics
- **Hors scope de ces URLs :** User Data Streams (compte), ordres, clés API

IchiVol est **déjà aligné** : proxy Vite + engine Python pointent vers `data-api.binance.vision` (pas `api.binance.com` trading).

Conséquences produit :

1. UI et docs parlent de **symboles / marché**, pas d’« compte Binance ».  
2. Aucune clé API exchange n’est requise pour le screener Phase 1 (données publiques).  
3. `MarketDataAdapter` ≠ `ExecutionAdapter`.  
4. Un signal IchiVol doit pouvoir rester **signal-only** (pas d’exécution).  
5. Quand le live arrivera : mapping symbole data → symbole venue d’exécution (ex. `BTCUSDT` feed → paire chez **ton** broker).  
6. Ne jamais brancher User Data Stream / signed trading endpoints dans le chemin « market data ».

---

## 1. Ce que tu calcules toi-même vs ce que tu récupères

| Fonction | Données nécessaires | Gratuit ? | Source data | Calcul |
|----------|---------------------|-----------|-------------|--------|
| Ichimoku | OHLC | ✅ | Binance (ou autre) | **Moteur Python** |
| RVOL | Volume + historique | ✅ | idem | **Moteur** |
| Price Action / HH-HL | OHLC | ✅ | idem | **Moteur** |
| Support / résistance | OHLC | ✅ | idem | **Moteur** |
| ATR | OHLC | ✅ | idem | **Moteur** |
| MTF | OHLC multi-TF | ✅ | idem | **Moteur** |
| VWAP / AVWAP | Prix + volume | ✅ | idem | **Moteur** |
| Volume Profile | OHLCV ou trades | ✅/⚠️ | Binance | **Moteur** (précision = granularité) |
| CVD approx. | Trades / taker | ✅ | Binance | **Moteur** |
| Open Interest | Futures | ✅ | Binance / Bybit | Lecture + normalise |
| Funding | Futures | ✅ | Binance / Bybit | Lecture + normalise |
| Temps réel | WebSocket | ✅ | Binance / Bybit | Ingest |
| Backtest | Historique stocké | ✅ | **ta DB** | **Moteur** |

**Interdit Phase 1–V1 :** acheter une API qui te renvoie « Ichimoku ready » / « signal RVOL ».  
Tu contrôles les règles → tu contrôles le backtest.

---

## 2. Trois niveaux de données (progression)

```
NIVEAU 1 — OHLCV                    ← maintenant / V1
├── Ichimoku
├── RVOL
├── ATR
├── Price Action / Structure
├── MTF
└── VWAP

NIVEAU 2 — TRADES                   ← quand la participation doit être plus fine
├── CVD / Volume Delta
├── Buy/Sell pressure
└── Volume Profile plus précis

NIVEAU 3 — DERIVATIVES              ← contexte, pas direction Ichimoku
├── Open Interest
├── Funding
├── Long/Short ratio
└── Futures positioning
```

Nuance Volume Profile / CVD : utiles en OHLCV approximatif ; **fins** seulement avec trades. Ne bloque pas V1.

Niveau 3 = **contexte / risque / participation dérivés**, jamais un droit de changer la direction Ichimoku seul.

---

## 3. Architecture data (Phase 1 — zéro abonnement)

```
     MarketDataAdapter(s)          ExecutionAdapter(s)
     ─────────────────────         ───────────────────
     Binance public OHLCV    ≠     PaperBroker (défaut)
     Bybit OI + Funding      ≠     (vide / stub)
     OKX (optionnel)         ≠     LiveBroker??? (plus tard, au choix)
            │                            │
            ▼                            │
     ┌──────────────┐                    │
     │ DATA ENGINE  │  normalize candles │
     │ + indicators │  (symbole canonique)│
     └──────┬───────┘                    │
            ▼                            │
     DECISION ENGINE                     │
     Structure → Participation           │
     → Location → Regime → Risk          │
            │                            │
            ▼                            ▼
         IchiVol UI ──────────────► order? only via ExecutionAdapter
```

Phase 1 concrète :

```
BINANCE (data only)
   ├── Spot OHLCV ──► Ichimoku, RVOL, Structure, ATR, MTF, VWAP…
BYBIT (data only, optionnel tôt)
   └── OI + Funding ──► métadonnées régime / crowding
              │
              ▼
        DATA ENGINE (Python calcule tout)
              │
              ▼
        DECISION ENGINE
              │
              ▼
        Paper / Signal-only  (pas de venue live figé)
```

---

## 4. Adapters — contrat mental

### MarketDataAdapter

- `list_symbols()`, `fetch_ohlcv(symbol, tf, limit)`, plus tard `fetch_trades`, `fetch_oi`, `subscribe_ws`
- Sortie **normalisée** : timestamps UTC, OHLCV float, `provider` en métadonnée, **pas** de logique Ichimoku dedans
- Déjà amorcé côté front (`src/lib/sources/*`) et engine (`market_data/`) — à unifier progressivement

### ExecutionAdapter

- `place_order`, `cancel`, `positions`, `balances` (paper d’abord)
- **Aucun** appel Binance trade API en Phase 1
- Live = plugin choisi plus tard (broker, autre CEX, DEX…) sans réécrire le Decision Engine

### Canonical symbol

Interne IchiVol : ex. `BTC-USDT` ou `asset_id` DB.  
Chaque adapter mappe vers son id natif (`BTCUSDT`, `BTCUSDT` Bybit, etc.).

---

## 5. Quand une API payante devient pertinente

**Phase 1 (maintenant)** : squelette `MarketDataProvider` + Binance Vision crypto only — **zéro abonnement**.

**Phase 1b — multi-actifs (dès que le squelette `/universe` est vert)** : un **seul** adaptateur multi-classes en plus de Binance.

Décision produit initiale (recherche 2026-09-15) :

| Rang | Provider | Rôle IchiVol |
|------|----------|--------------|
| 🥇 | **Twelve Data** | Premier adaptateur FX / métaux / actions / indices / ETF (+ crypto possible) |
| 🥈 | **EODHD** | Benchmark historique / backtest profond (prototype parallèle 48h) |
| 🥉 | Alpha Vantage | Tests ponctuels seulement (25 req/jour = mort pour screener) |
| — | Marketstack | Rejeté comme cœur (trop actions/EOD) |
| — | Yahoo / yfinance | **Interdit** comme source produit |

**Révision Phase 1c (2026-09-15, même jour, après mise à l'épreuve réelle)** : Twelve Data Basic (8 crédits/min, 800/jour) s'est révélé trop juste dès que le catalogue couvre 7 instruments non-crypto à la fois (EURUSD/GBPUSD/USDJPY/XAUUSD/XAGUSD/AAPL/TSLA), et SPX/NDX restaient bloqués derrière son plan payant. Recherche d'alternatives gratuites/freemium (voir conversation du 2026-09-15) a identifié **biquote.io** : REST gratuit et sans clé, miroirs CFD MetaTrader 5, testé en direct avec succès sur FX/métaux/indices/énergie. Un seul vrai piège trouvé en le testant réellement (pas en se fiant à la doc marketing) : chaque appel est plafonné côté serveur à ~100 bougies quel que soit le `count` demandé — c'est donc un **flux live**, pas une source de backfill historique en un coup ; la profondeur s'accumule dans la DB au fil des appels via `app/market_data/collector.py` (idempotent), exactement comme n'importe quel flux live devrait le faire. Autre piège : la liste `/api/symbols` de biquote annonce `hasData:false` même pour des tickers qui renvoient bel et bien des données réelles (EURUSD, AAPL…), et certains tickers intuitifs n'ont aucune donnée (`SPX500`, `NAS100`, `WTI` renvoient des bougies vides) alors que leurs équivalents CFD (`US500`, `USTEC`, `USOIL`) fonctionnent — chaque `provider_symbol` du catalogue a donc été vérifié un par un contre l'endpoint `/ohlc` réel, jamais deviné depuis la liste de symboles.

Nouveau partage des rôles :

| Provider | Rôle IchiVol | Pourquoi |
|----------|--------------|----------|
| **biquote.io** | FX, métaux, indices, énergie | Gratuit, sans clé, pas de quota documenté ; volume toujours 0 (CFD) mais `tickVolume` réel en remplacement — strictement mieux que le 0 plat que Twelve Data renvoyait déjà pour ces classes |
| **Twelve Data** | Actions uniquement (AAPL, TSLA) | Volume d'échange réel utile pour RVOL — seule classe où ça compte encore ; ne consomme plus que 2 symboles sur son budget 8 crédits/min au lieu de 7 |
| EODHD | Benchmark historique / backtest profond (inchangé) | — |
| Yahoo / yfinance | **Toujours interdit** comme source produit | — |

Mapping catalogue (état réel, `app/universe/catalog.py`) :

```
BTCUSDT / ETH…     → binance          (provider_symbol = symbole Binance natif)
EURUSD, GBPUSD…    → biquote          (provider_symbol = EURUSD, GBPUSD… -- identique à l'id)
XAUUSD, XAGUSD…    → biquote          (provider_symbol = XAUUSD, XAGUSD… -- identique à l'id)
SPX                → biquote          (provider_symbol = US500, PAS SPX500)
NDX                → biquote          (provider_symbol = USTEC, PAS NAS100)
WTI                → biquote          (provider_symbol = USOIL, PAS WTI)
AAPL, TSLA…        → twelve_data      (provider_symbol = AAPL, TSLA -- volume réel)
```

Le moteur Ichimoku/RVOL **ne connaît pas** le provider — seulement OHLCV normalisé.

**Licence SaaS** : plan gratuit Twelve Data = perso/non commercial (toujours vrai pour AAPL/TSLA). biquote.io est gratuit et sans clé mais ses conditions d'usage commercial ne sont pas formalisées publiquement — à re-vérifier directement avec eux avant de facturer IchiVol à des tiers. Redistribuer des données à des users = à valider provider par provider. Prototype local OK tel quel.

**Pas maintenant** : 4 APIs en parallèle, ni payer pour des indicateurs tout faits.

---

## 5b. Contrat bougie enrichi (obligatoire pour RVOL multi-classes)

Le volume n’a **pas** le même sens partout. Le normaliseur doit porter :

```text
OHLCVBar {
  timestamp, open, high, low, close, volume,
  volume_type,   # exchange | tick | reported | none
  source,        # binance_vision | twelve_data | …
  symbol,        # id canonique IchiVol
  timeframe
}
```

| Classe | volume_type typique | Impact RVOL |
|--------|---------------------|-------------|
| Crypto (Binance) | `exchange` | OK tel quel |
| Actions | `exchange` | OK tel quel |
| Forex | `tick` ou `none` | RVOL = **proxy** — à labeller / éventuellement désactiver |
| Métaux via vendor | selon feed | Ne pas confondre avec volume LME |

XAUUSD : toujours `provider_symbol` + métadonnées vendor — **jamais** « chercher XAUUSD naïvement ».

---

## 6. Ce qu’on ne fait pas

1. Vendre IchiVol comme « bot Binance ».  
2. Coupler décision et `binance.create_order`.  
3. Payer TradingView / APIs d’indicateurs tout faits pour le cœur.  
4. 15 APIs data en parallèle dès le jour 1 — **Binance Vision + (Phase 1c) biquote.io + Twelve Data (actions seulement)**, EODHD en benchmark seulement.  
5. Laisser le front calculer une vérité différente du backtest Python (cible = une source de vérité indicateurs).  
6. Mettre Yahoo Finance / yfinance au cœur du produit.

---

## 7. Alignement roadmap V1

| Priorité data | Pour quel étage décision |
|---------------|--------------------------|
| OHLCV Binance (déjà) | Setup Ichimoku + RVOL + ATR + Structure |
| Persist candles DB | Backtest / calib |
| MTF OHLCV | Contexte |
| Trades (N2) | CVD / VP fin — après V1 stable |
| OI/Funding Bybit (N3) | Régime / crowding — optionnel tôt, pas bloquant |
| Execution live | **Hors scope** jusqu’à paper + preuve |

---

## 8. Phrase à retenir

> **Les adaptateurs nourrissent le cerveau ; IchiVol décide ; le lieu où tu trades reste un choix ouvert — paper d’abord, venue réelle plus tard, jamais hardcodée dans la stratégie.**

Crypto Phase 1 = Binance Vision (data-only). Multi-actifs : FX/métaux/indices/énergie = biquote.io (Phase 1c, gratuit/sans clé), actions = Twelve Data (Phase 1b, volume réel) — même contrat `MarketDataProvider` des deux côtés.
