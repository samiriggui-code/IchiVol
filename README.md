# IchiVol — Ichimoku × Volume

App web **screener + chart** : un signal Ichimoku ne compte que s’il est **confirmé par le volume relatif (RVOL ≥ 1.5)**.

## Contenu

| Dossier | Description |
|---------|-------------|
| [`ichivol-app/`](ichivol-app/) | App Vite + React + TypeScript + lightweight-charts |
| [`ichimoku-volume/`](ichimoku-volume/) | Indicateur Pine Script (TradingView) |

## Lancer l’app

```bash
cd ichivol-app
npm install
npm run dev
```

→ http://localhost:5173

Proxy Vite : `/binance` → `https://data-api.binance.vision`

```bash
npm run build
```

## Principe

1. Ichimoku 9/26/52/26
2. Volume coloré selon biais cloud
3. Signaux TK cross / breakout cloud **uniquement si RVOL confirme**
4. Screener ~20 paires USDT liquides

Voir [`ichivol-app/SPEC.md`](ichivol-app/SPEC.md) pour la décision de stack.
