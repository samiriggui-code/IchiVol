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
cd ichivol-app
npm install
npm run dev
```

→ http://localhost:5173/ — landing GSMS CRM style (dark/light)  
→ `/login` — admin unique MVP (`admin` / `ichivol`)  
→ `/app` — cockpit (auth session requise)

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

## Agent IA (explicateur de signaux)

Panneau `AgentPanel` (3 modes : expliquer un signal, recherche théorique, idée de marché sur le screener), branché sur un petit backend séparé dans [`server/`](server/). L'agent est bridé pour ne jamais inventer une valeur de marché — voir [`server/README.md`](server/README.md) pour le détail du référentiel anti-hallucination.

Lancement (trois process — ou `npm run dev:stack` depuis `ichivol-app/`) :

```bash
# terminal 1 — moteur Python
cd engine
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# terminal 2 — backend agent / auth / proxy /api/engine → :8000
cd server
npm install
cp .env.example .env   # renseigner JWT_SECRET + ENGINE_URL=http://127.0.0.1:8000
npm run dev             # http://localhost:8787

# terminal 3 — app
cd ..
npm run dev              # http://localhost:5173, proxy /api -> :8787
```

Chaîne locale : **Vite `:5173` → Node `:8787` → Python `:8000`**. Sans le Node, `/api/*` renvoie 502 même si Python tourne.

⚠️ `dotenv` ne surcharge pas une variable déjà présente dans l'environnement système : si `ANTHROPIC_API_KEY` (ou autre) est déjà définie globalement sur la machine, le serveur l'utilisera même si `server/.env` est vide.
