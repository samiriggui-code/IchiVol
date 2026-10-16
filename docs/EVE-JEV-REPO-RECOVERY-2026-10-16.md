# Ève / JEV — récupération des repos (2026-10-16)

> Clones locaux (non runtime) : `ichivol-app/research/jev/` (+ QuantDinger aussi sous `OpenByteInc/QuantDinger`)  
> Branche produit : `cursor/eve-intelligence-v1-8626` / PR #178  
> Handoff : [`HANDOFF-EVE-INTELLIGENCE-V1-2026-10-16.md`](./HANDOFF-EVE-INTELLIGENCE-V1-2026-10-16.md)

**Principe universel (tous les repos) :** *Jev juge, le code exécute.*  
Seuils, vetoes et ordres restent déterministes. Jamais de portefeuille Eve. Jamais de trading réel depuis Ève sans Risk Kernel + `EVE_PAPER_AUTONOMY`.

---

## Repos confirmés (5)

| # | Clone | Upstream | Rôle |
|---|---|---|---|
| 1 | `feder-cr-jev` | [feder-cr/jev](https://github.com/feder-cr/jev) | **jevos-v4** — runtime System One local (déjà sur VPS) |
| 2 | `jarrodwatts-jev-trader` | [jarrodwatts/jev-trader](https://github.com/jarrodwatts/jev-trader) | Template dry-run + flux événements / SSE |
| 3 | `buberlo-jev-trader` | [buberlo/jev-trader](https://github.com/buberlo/jev-trader) | Architecture la plus stricte (6 jugements, fallback, calib, risk) |
| 4 | `Gamma-Software-jev-signals-lab` | [Gamma-Software/jev-signals-lab](https://github.com/Gamma-Software/jev-signals-lab) | Batterie multi-questions + règles en code, paper-only |
| 5 | `OpenByteInc-QuantDinger` | [OpenByteInc/QuantDinger](https://github.com/OpenByteInc/QuantDinger) | **OS trading complet** — gate Jev + Event Radar + Settings schema + protection + paper virtuel (voir audit dédié) |
| 6 | `aowang-ai-jev-trade` | [aowang-ai/jev-trade](https://github.com/aowang-ai/jev-trade) | Fork Hyperliquid live de jarrodwatts — **audité, pas d’import runtime** ([audit](./EVE-AOWANG-JEV-TRADE-AUDIT-2026-10-16.md)) |

```bash
# QuantDinger (chemin demandé Samir)
git clone --depth 1 https://github.com/OpenByteInc/QuantDinger.git OpenByteInc/QuantDinger

cd ichivol-app/research/jev
git clone --depth 1 https://github.com/feder-cr/jev.git feder-cr-jev
git clone --depth 1 https://github.com/jarrodwatts/jev-trader.git jarrodwatts-jev-trader
git clone --depth 1 https://github.com/buberlo/jev-trader.git buberlo-jev-trader
git clone --depth 1 https://github.com/Gamma-Software/jev-signals-lab.git Gamma-Software-jev-signals-lab
# junction ou clone → OpenByteInc-QuantDinger
```

(les arbres sont gitignorés sauf `research/README.md`)

---

## Déjà récupéré dans IchiVol (PR #178)

| Pattern | Source | Où chez nous |
|---|---|---|
| Wire `/v1/systemone` NOUL/CHOICE/SCORE | feder-cr + TypeSafe | `app/jev/adapter.py`, `providers.py` |
| Provider jevos-v4 défaut + typesafe | feder-cr / TypeSafe | `JEV_URL=http://jevos-v4:8017` |
| Modes ≠ 4 LLM ; primitives calibrées | étude + buberlo « atomic » | `app/eve/modes.py`, `primitive_study.py` |
| Risk jamais délégué au modèle | buberlo `risk/limits.py` | Risk Kernel + Guardian advisory |
| Paper / dry-run par défaut | jarrodwatts + Gamma | `EVE_PAPER_AUTONOMY=false` |
| Outcomes séparés de decision_time | buberlo triples | `decision_time_json` immuable / `outcome_json` |
| Calibration ≠ fine-tune | buberlo + handoff | `app/eve/calibration.py` (observe + propose) |
| Pre-trade gate atomique (5 CHOICE) | QuantDinger `ai_decision_filter.py` | À porter sur Guardian / paper dry-run (pas live) |

### QuantDinger — audit **complet** (pas seulement le gate)

**Doc détaillée :** [`EVE-QUANTDINGER-AUDIT-2026-10-16.md`](./EVE-QUANTDINGER-AUDIT-2026-10-16.md)

| Couche | Ce qu’on retient |
|---|---|
| **Front** | Sources Vue **hors repo** ; on reprend le **contrat** Settings schema-driven (Basic/Advanced), timeline `/ai-decisions`, Event Radar UI, strategy `# @param` |
| **Settings / options** | Knobs `JEV_*`, `EVENT_RADAR_*`, calib, `AGENT_LIVE_TRADING_ENABLED`, caps notional — mappables IchiVol Settings |
| **Gate Jev** | 5 CHOICE atomiques (`ai_decision_filter.py`) + contexte PIT |
| **Event Radar** | News/SEC/calendar → JEV relevance/impact |
| **Protection / paper** | `ProtectionSpec`, fee-aware trailing, comptes virtuels signal-only |
| **Calib / reflection** | Seuils depuis outcomes (observe-only chez Ève) |
| **MCP / Agent** | Scopes + confirms paper ; pas le live |

**Ne pas** récupérer : billing, SaaS multi-tenant, brokers live, fail-open live, Kafka V6, mobile H5.

---

## Récupéré / appliqué cette session locale

| Item | Source | Livrable |
|---|---|---|
| Timeline dossier (decision → followups → outcome) | jarrodwatts events + buberlo triples | `build_dossier_timeline` + champ `timeline` API + UI panel |
| Carte de récupération | les 5 | ce document |
| Clone QuantDinger | Samir | `OpenByteInc/QuantDinger` + junction `research/jev/OpenByteInc-QuantDinger` |

---

## À récupérer ensuite (priorisé, sans casser les garde-fous)

### P1 — Fallback ladder (buberlo + QuantDinger)
Quand JEV down / late / low confidence :
`healthy+conf → size normal` · `low conf → reduce` · `late → HOLD` · `JEV down → heuristique` · `limit breach → kill`.  
QuantDinger : Jev → LLM fallback (chez nous : Jev → modes déterministes, **pas** OpenRouter pour System One).

### P2 — Batterie multi-signaux / pre-trade gate (Gamma + buberlo + QuantDinger)
Une requête, N questions atomiques puis **règles en code**.  
QuantDinger 5 CHOICE = modèle fort pour enrichir Guardian avant `paper-submit` dry-run.

### P3 — Métriques calib Brier / ECE (buberlo `calibration/metrics.py`)
Nécessite stocker les probabilités JEV au `decision_time` puis les croiser aux outcomes.  
Ajout possible dans `observe_from_dossiers` **sans** auto-appliquer de policy.

### P4 — UI flux temps réel (jarrodwatts SSE)
Optionnel : stream follow-up / dry-run ; pas bloquant pour V1/V2.

### Ne pas récupérer
- Exécution live / wallets / Monad / Hyperliquid / brokers QuantDinger  
- Market-making A-S pricing  
- Création d’un portefeuille « Eve »  
- Billing / multi-tenant QuantDinger  
- Auto-apply de Platt / thresholds sans revue Samir  

---

## Mapping modes Ève ↔ primitives (rappel)

| Mode | Primitives (étude) | Inspiration repo |
|---|---|---|
| Analyst | SCORE | Gamma technical_setup / short_term_risk |
| Challenger | NOUL + CHOICE | buberlo direction + toxic_flow |
| Guardian | NOUL + SCORE | buberlo risk vetoes (advisory only) |
| Shadow | NOUL + CHOICE + SCORE | jarrodwatts independent decision audit |

---

*Fin — session locale post-cloud 2026-10-16.*
