# IchiVol — Ichimoku × Volume

App web **screener + chart** : un signal Ichimoku ne compte que s’il est **confirmé par le volume relatif (RVOL ≥ 1.5)**.

## Décision produit / stack

| Choix | Pourquoi (marché) |
|-------|-------------------|
| **Web app** (pas mobile-first) | TradingView / Finviz / TrendSpider gagnent sur le web charting |
| **Screener + chart** | Un indicateur Pine = 1 symbole ; le gap = scanner multi-paires Ichimoku×volume |
| **Crypto (Binance Vision)** | OHLCV + volume gratuit ; actions = API payantes |
| **Vite + React + TypeScript** | Stack standard fintech indie |
| **lightweight-charts** | Lib chart OSS de TradingView, dominante hors Advanced Charts payant |

## Lancer

```bash
cd scripts/trading/ichivol-app
npm install
npm run dev
```

→ http://localhost:5173  

Proxy Vite : `/binance` → `https://data-api.binance.vision` (plus accessible que `api.binance.com` selon la région).

```bash
npm run build
```

## Principe

1. Ichimoku 9/26/52/26  
2. Volume coloré selon biais cloud  
3. Signaux TK cross / breakout cloud **uniquement si RVOL confirme**  
4. Screener ~20 paires USDT liquides  

Companion Pine Script : [`../ichimoku-volume/`](../ichimoku-volume/).
