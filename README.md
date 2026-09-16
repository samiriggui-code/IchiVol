# IchiVol — Ichimoku × Volume

App web **screener + chart** : un signal Ichimoku ne compte que s’il est **confirmé par le volume relatif (RVOL ≥ 1.5)**.

## Contenu

| Dossier | Description |
|---------|-------------|
| [`ichivol-app/`](ichivol-app/) | App Vite + React + TypeScript + lightweight-charts |
| [`ichimoku-volume/`](ichimoku-volume/) | Indicateur Pine Script (TradingView) |

## Lancer l’app

Le projet a 3 process : le front (Vite, 5173), le serveur (Express, 8787) et le moteur Ichimoku×RVOL (Python/FastAPI, 8000). Setup une fois chacun (`npm install` dans `ichivol-app/` et `ichivol-app/server/`, `python -m venv .venv && pip install -r requirements.txt` dans `ichivol-app/engine/` — voir [`ichivol-app/engine/README.md`](ichivol-app/engine/README.md)), puis à la racine :

```bash
npm run dev
```

Lance les 3 process en parallèle (sortie préfixée `[vite]`/`[server]`/`[engine]`, un seul Ctrl+C les arrête tous) → http://localhost:5173

Proxy Vite : `/binance` → `https://data-api.binance.vision`, `/api` → serveur Express (qui relaie `/api/engine/*` vers le moteur Python).

```bash
cd ichivol-app && npm run build
```

## Principe

1. Ichimoku 9/26/52/26
2. Volume coloré selon biais cloud
3. Signaux TK cross / breakout cloud **uniquement si RVOL confirme**
4. Screener ~20 paires USDT liquides

**North star (verrouillée) :** [`docs/TRADING_ARCHITECTURE_V2.md`](docs/TRADING_ARCHITECTURE_V2.md) — 5 questions (Direction → Participation → Location → Régime → Risque).  
**Cahier des charges (backlog maître) :** [`docs/CAHIER-DES-CHARGES.md`](docs/CAHIER-DES-CHARGES.md).  
**Méthodes V1→V3 :** [`docs/METHODS-ROADMAP.md`](docs/METHODS-ROADMAP.md).  
**Arborescence V2 (pages + LLM) :** [`docs/APP-ARBORESCENCE-V2.md`](docs/APP-ARBORESCENCE-V2.md).  
**Données :** [`docs/MARKET-DATA-STRATEGY.md`](docs/MARKET-DATA-STRATEGY.md) — feeds gratuits ≠ lieu d’exécution ; indicateurs en local.  
**Claude (engine) — realign :** [`docs/HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md`](docs/HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md).

Voir [`ichivol-app/SPEC.md`](ichivol-app/SPEC.md) pour la décision de stack.
