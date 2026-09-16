# IchiVol — Arborescence app V2 (pages front + rôles LLM)

**Statut : VERROUILLÉ** — cible produit quand V2 est atteint (après V1 Structure+ATR + preuve backtest).  
North star : [`TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md) · Agents : [`HANDOFF-AGENT-CONCEPT.md`](./HANDOFF-AGENT-CONCEPT.md)

---

## 1. Carte mentale V2

```
ichivol/
├── public web
│   ├── /                 Landing
│   └── /login            Auth
│
└── /app/*                Cockpit (session)
    ├── overview          Tableau de bord (screener + teaser contexte)
    ├── market            Screener + chart (cœur signal)
    ├── decisions         Pipeline à étages + journal
    ├── watchlist         Pins / alertes (V2)
    ├── paper             Paper trading + positions (V2)
    ├── performance       Calib / hit-rate / Brier (V2)
    ├── backtests         Expériences & walk-forward
    ├── context           Détail macro (zoom de l’aperçu Overview)
    ├── academy           KB trading (lecture)
    ├── agent             Copilot LLM (chat + skills)
    └── settings          Clés, seuils, sources, risk prefs
```

**Direction produit (ne pas confondre les pages) :**

| Page | Job |
|------|-----|
| **Overview** | « Où en est mon cockpit ? » — compteurs décisions + aperçu macro |
| **Marché** | « Que fait ce symbole ? » — chart + signaux live |
| **Décisions** | « Que dit la méthode ? » — pipeline 5 portes |
| **Contexte** | « Quel climat crypto ? » — détail de l’aperçu Overview, **pas** un 2ᵉ screener |
| **Backtests** | « Est-ce que ça tient historiquement ? » |

**Principe UI :** le **moteur quantitatif** produit la décision ; le **LLM** explique et propose des actions **confirmées**. Jamais l’inverse.

---

## 2. Arborescence fichiers cible (repos)

```
IchiVol/
├── docs/                          # North star + handoffs
├── ichimoku-volume/               # Pine companion (TradingView)
└── ichivol-app/
    ├── src/                       # Front React
    │   ├── pages/
    │   │   ├── LandingPage.tsx
    │   │   ├── LoginPage.tsx
    │   │   ├── OverviewPage.tsx
    │   │   ├── MarketPage.tsx          # screener + chart
    │   │   ├── DecisionsPage.tsx       # étages + détail décision
    │   │   ├── WatchlistPage.tsx       # V2
    │   │   ├── PaperTradingPage.tsx    # V2
    │   │   ├── PerformancePage.tsx     # V2
    │   │   ├── BacktestsPage.tsx
    │   │   ├── ContextPage.tsx         # ou ContextPanel dédié
    │   │   ├── AcademyPage.tsx         # V2 (KB)
    │   │   ├── AgentPage.tsx           # V2 (copilot plein écran ; panel reste OK)
    │   │   └── SettingsPage.tsx
    │   ├── components/
    │   │   ├── Screener.tsx
    │   │   ├── PriceChart.tsx
    │   │   ├── DecisionPipelinePanel.tsx   # étages 1→6
    │   │   ├── AgentPanel.tsx              # copilot (existant)
    │   │   └── …
    │   └── lib/                       # types, sources marché (affichage)
    │
    ├── server/                    # Node/Express — auth, settings, copilot LLM
    │   └── src/
    │       ├── agent/             # Copilot + skills allowlist
    │       ├── knowledge/         # RAG Academy
    │       ├── auth/
    │       ├── execution/         # PaperBroker (V2)
    │       └── …
    │
    └── engine/                    # Python — stratégie déterministe
        └── app/
            ├── indicators/        # ichimoku, rvol, atr, structure
            ├── agents/            # StrategyAgents (PAS de LLM)
            ├── decision/          # pipeline à étages (remplace combiner ×)
            ├── consensus/         # V2 only, après preuve
            ├── screener/
            ├── backtest/
            ├── risk/              # sizing ATR / caps (V1.5–V2)
            └── …
```

---

## 3. Pages front — rôle de chaque écran

| Route | Page | Rôle | Données | LLM ? |
|-------|------|------|---------|-------|
| `/` | Landing | Produit / promesse Ichimoku×RVOL×ATR | Statique | Non |
| `/login` | Login | Session | Auth | Non |
| `/app/overview` | Overview | Santé : résumé screener + teaser contexte | Screener + macro compact | Optionnel |
| `/app/market` | **Marché** | **Cœur ops** : screener, chart cloud+volume, signaux live | Engine + OHLCV | Panel latéral OK |
| `/app/decisions` | Décisions | Détail **pipeline à étages** + invalidation + journal | Decision Engine | **Oui** : expliquer une décision figée |
| `/app/context` | Contexte | **Détail** de l’aperçu Overview : F&G historique, top marchés, dominance élargie. Régime macro — **ne vote pas** Ichimoku | CoinGecko / Alt.me | Relier climat ↔ biais |
| `/app/watchlist` | Watchlist (V2) | Symboles pinnés, seuils alerte RVOL/ATR | User prefs + screener | Propose pins (confirm) |
| `/app/paper` | Paper (V2) | Positions paper, fills, PnL | PaperBroker | Expliquer un trade clos |
| `/app/performance` | Performance (V2) | Hit-rate, Brier, calib agents, drift | DB perf / calib | Commenter un drift (pas recalibrer seul) |
| `/app/backtests` | Backtests | Runs, params, walk-forward, compare V1 vs +momentum | Engine backtest | Résumer un run (chiffres injectés) |
| `/app/academy` | Academy (V2) | Docs KB (Ichimoku, volume, breakout…) | `server/knowledge` | Mode `research` |
| `/app/agent` | Copilot (V2) | Chat plein écran + historique threads | Skills + mémoire | **Oui** — seul siège LLM conversationnel |
| `/app/settings` | Settings | Clés LLM, seuils RVOL/ATR, sources, risk caps | Settings DB | Non (config) |

### Déjà en place aujourd’hui

`/` · `/login` · `/app/overview` · `/app/market` · `/app/context` · `/app/decisions` · `/app/backtests` · `/app/settings` (+ `AgentPanel` embarqué).

### À ajouter pour V2 UI

`watchlist` · `paper` · `performance` · `academy` · `agent` (route dédiée) · panneau **DecisionPipeline** (étages visibles).

---

## 4. Ce que l’utilisateur voit sur une décision (V2)

Sur `/app/decisions/:id` (ou sheet) :

```
SETUP        Ichimoku     LONG          cloud break + TK
VALIDATION   RVOL         2.1×          ACTIF (≥ 1.5)
CONTEXTE     Structure    OK            HH/HL + break R1 H1
             MTF          Aligné        H4 bull / H1 signal
RÉGIME       ATR          Normal        tradable
SCORE        qualité      0.78          risque 0.42
────────────────────────────────────────
DECISION     BUY
INVALIDATION close sous Kijun / RVOL retombe < 1.2
```

Copilot : bouton **« Expliquer »** → skill `explain_signal` avec **payload chiffré injecté** (jamais inventé).

---

## 5. Rôles des agents LLM (couche B uniquement)

IchiVol a **un seul agent conversationnel** (Copilot), pas N personas qui votent.

```
                    ┌─────────────────────┐
   User  ──────────►│  COPILOT (LLM)      │
                    │  server/src/agent   │
                    └──────────┬──────────┘
                               │ skills allowlist
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
   explain_*              research               actions*
   (décision/             (Academy KB            (pin, save,
    signal/trade)          + citations)           refresh…)
         │                     │                     │
         └──────────┬──────────┴──────────┬──────────┘
                    ▼                     ▼
            chiffres = API/DB        confirm user
            (anti-hallu)             avant mutation
```

### Skills autorisés (cible V2)

| Skill | Page typique | Fait | Ne fait pas |
|-------|--------------|------|-------------|
| `explain_signal` | Market, Decisions | Explique setup / RVOL / étages avec chiffres fournis | Inventer RVOL ou biais |
| `explain_decision` | Decisions | Parcourt étages 1→6 + invalidation | Changer la décision engine |
| `research` | Academy, Agent | Répond via KB + citations | Donner un “trade sure” sans disclaimer |
| `trade_idea` | Market, Agent | Idée **à partir du screener réel** + disclaimer | Contredire un NO_TRADE engine sans le dire |
| `summarize_backtest` | Backtests | Résume métriques injectées | Recalculer un sharpe de tête |
| `summarize_performance` | Performance | Commente drift / hit-rate fournis | Déployer une calib tout seul |
| `save_decision` | Decisions | Persiste après **confirm** | Écrire sans confirm |
| `pin_symbol` | Watchlist, Market | Pin après confirm | — |
| `refresh_screener` | Market | Relance scan | — |
| `propose_paper_trade` | Paper, Decisions | Propose entrée paper alignée décision | Envoyer live / broker réel |

### Interdit aux LLM (non négociable)

- Voter LONG/SHORT dans le Decision Engine  
- Multiplier ou remplacer le score des StrategyAgents  
- Inventer OHLC, RVOL, ATR, scores  
- Ordres live, retraits, appels hors allowlist  
- “Bureau” style 19 agents GrokDesk qui se firent entre eux  

### StrategyAgents (couche A) — rappel

| Agent | Dimension | LLM ? |
|-------|-----------|-------|
| `ICHIMOKU_AGENT` | Structure / direction | Non |
| `RVOL_AGENT` | Participation | Non |
| `STRUCTURE_AGENT` | Contexte prix / S/R / HH-HL | Non |
| `VOLATILITY_AGENT` | Régime ATR / risk | Non |
| `MOMENTUM_AGENT` | Optionnel V2+ | Non |
| Consensus (pondération) | Agrégation post-preuve | Non |

Le LLM peut **narrativer** leur sortie ; il ne la **produit** pas.

---

## 6. Navigation cible (shell)

```
IchiVol
├── Vue d’ensemble
├── Marché              ← ops quotidien
├── Décisions           ← pipeline + journal
├── Watchlist
├── Paper trading
├── Performance
├── Backtests
├── Contexte
├── Academy
├── Copilot             ← seul chat LLM
└── Paramètres
```

Panel copilot **flottant / latéral** reste utile sur Marché & Décisions ; `/app/agent` = historique long + skills avancés.

---

## 7. Flux bout-en-bout (une opportunité)

```
1. Screener (Market)     → lignes WATCH / candidats
2. Decision Engine       → étages 1→6 → BUY|SELL|WATCH|NO_TRADE
3. UI Decisions          → affiche portes + invalidation
4. Copilot (optionnel)   → explain_decision (chiffres injectés)
5. User confirm          → paper trade (V2) ou save_decision
6. Résultat              → Performance + Backtest loop
7. Calib humaine         → Settings / StrategyCalibration (jamais auto-deploy LLM)
```

---

## 8. Mapping “maintenant → V2”

| Maintenant | V2 |
|------------|-----|
| Combiner `ichi × rvol` | Pipeline à étages |
| DecisionsPage basique | Étages visibles + invalidation |
| AgentPanel 3 modes | Skills étendus + `/app/agent` + threads |
| Pas de paper UI | `/app/paper` |
| BacktestsPage amorcée | Liée perf + compare agents |
| Pas Watchlist/Academy/Perf | Pages dédiées |
| Consensus absent | Seulement après preuve Structure+ATR |

---

## 9. Critère “V2 atteint”

- [ ] Pipeline à étages en prod (plus de `confidence = a * b` comme règle unique)  
- [ ] Structure + ATR dans le moteur et visibles en UI  
- [ ] Paper trading + journal résultats  
- [ ] Performance / calibration consultables  
- [ ] Copilot = skills allowlist + anti-hallu + confirm mutations  
- [ ] Momentum / Consensus **uniquement** si backtest V1 le justifie  
- [ ] Phrase fondatrice respectée partout (code + UI + prompts)
