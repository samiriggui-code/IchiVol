# Audit `aowang-ai/jev-trade` (cahier §6 — dépôt C)

> Clone local : `ichivol-app/research/jev/aowang-ai-jev-trade`  
> Upstream : https://github.com/aowang-ai/jev-trade · MIT · main @ 2026-09-21 push  
> Description GitHub : « Live Jev trader on Hyperliquid »

---

## 1. Existence / licence / maintenance

| Critère | Constat |
|---|---|
| Existe | Oui, public |
| Licence | MIT (fork déclaré de jarrodwatts/jev-trader) |
| Stack | Bun bot + Next dashboard `web/` |
| Activité | Repo récent (2026), desk live `jev-trade.com` |

---

## 2. JEV réel ?

**Oui.** `src/model.ts` appelle System One via `@typesafe-ai/sdk` / Vercel Gateway (`MODEL=jev`).  
Mock momentum si pas de clé. Décisions : long/short + open/close/hold + probabilités.

Pas de surface NOUL/CHOICE/SCORE nommée comme IchiVol — c’est un **bot tick** (book → Jev → ordre), pas une batterie de modes Analyst/Challenger/Guardian.

---

## 3. Données / décision / risque / logs

| Couche | Contenu | Intérêt IchiVol |
|---|---|---|
| Market | Book Hyperliquid, depth, CVD, indicateurs | Déjà couvert par moteurs Python IchiVol |
| Décision | Un appel Jev / sleeve / tick | Moins riche que modes + gate Ève |
| Exécution | Wallets, Alo/Ioc, testnet/mainnet | **Hors scope** (live) |
| Dry-run | Clé absente / `DRY_RUN` | Pattern déjà repris via jarrodwatts |
| SSE | `/events` snapshot/block/quote/fill | Doublon jarrodwatts (P3 optionnel) |
| Risk | Pas de Risk Kernel IchiVol ; notional fixe | Ne remplace pas nos garde-fous |

---

## 4. Décision

**Ne pas importer de code dans le runtime Ève.**

Raisons :
1. Fork Hyperliquid **live** — cahier interdit brokers/wallets live.
2. Les idées utiles (dry-run, TypeSafe, SSE, late/hold) sont déjà absorbées via **jarrodwatts** + notre adapter.
3. Gamma / QuantDinger / buberlo apportent plus pour modes, gate et calib.

**Statut cahier §6 :** dépôt C **inspecté** — trou d’audit fermé.

---

*Audit local 2026-10-16 — lecture seule, pas d’intégration runtime.*
