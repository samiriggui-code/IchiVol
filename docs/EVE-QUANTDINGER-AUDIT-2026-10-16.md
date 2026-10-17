# Audit QuantDinger complet → IchiVol Ève (2026-10-16)

> Clone : `OpenByteInc/QuantDinger` @ `a26152e`  
> Junction research : `ichivol-app/research/jev/OpenByteInc-QuantDinger`  
> Complète (et corrige) la note trop étroite qui ne citait que `ai_decision_filter.py`.

**Constat honnête :** le front Vue **n’est pas dans ce dépôt OSS** (repo privé `QuantDinger-Vue` → image GHCR). On récupère le **contrat UI** via Settings schema + routes API. Le reste du backend est audité ci-dessous.

---

## 1. Surface produit

| Zone | Path | Contenu |
|---|---|---|
| Backend Flask | `backend_api_python/app/` | routes, services, workers, migrations |
| Settings (Basic/Advanced) | `routes/settings.py` (~2480 lignes) | `CONFIG_SCHEMA` + `ADVANCED_KEYS` → UI schema-driven |
| MCP | `mcp_server/` | tools paper/live sur `/api/agent/v1` |
| Docs produit | `docs/product/`, `AGENTS.md`, `ROADMAP.md` | intent + invariants |
| Compose | `docker-compose*.yml` | UI 8888, API 5000, mobile 8889, Kafka/Redis/PG |
| Front sources | **absent** | image `ghcr.io/openbyteinc/quantdinger-frontend` |

---

## 2. Front / écrans (inférés du contrat API)

| Écran | Preuve API | À récupérer pour IchiVol |
|---|---|---|
| **System Settings** Basic/Advanced | `GET/POST /api/settings/*` (`/schema`, `/values`, `/save`, `/test-connection`) | **Oui** — knobs JEV/Radar/Agent schema-driven (comme SettingsPage IchiVol) |
| **AI / LLM + JEV** | groupe schema `JEV_*`, providers | Mapping env Ève |
| **AI Agent** | `AGENT_LIVE_TRADING_ENABLED`, reflection, calibration, ensemble | Flags paper-only + calib |
| **Quick Trade + AI decisions** | `quick_trade*.py`, `/ai-decisions` | Timeline décisions (déjà amorcée Eve panel) |
| **Event Radar** | `quick_trade_event_radar.py` | Enrichir contexte news Ève |
| **Portfolio / monitors / alerts** | `routes/portfolio.py` | UI monitors paper |
| **Strategy params** (`# @param` → schéma) | `services/strategy_params.py` | Paramètres déclaratifs Lab |
| **Protection SL/TP/trail** | `strategy_v2/protection.py` | Aligner paper protection |
| **Backtest Center / Research** | `backtest_center.py`, `fast_analysis.py` | Secondaire |
| Credentials / Billing / Community / Mobile | routes dédiées | **Non** |

**Pattern UI clé :** le front ne hardcode pas les champs — il consomme `/api/settings/schema` avec `is_advanced`. À reproduire pour knobs Ève/JEV dans `SettingsPage.tsx`.

---

## 3. Settings / options (knobs utiles)

Source : `CONFIG_SCHEMA` + `.env.example` (un seul fichier runtime).

### JEV / intelligence

| Knob | Rôle |
|---|---|
| `JEV_API_KEY` / `JEV_BASE_URL` / `JEV_MODEL` | System One |
| `JEV_TIMEOUT_SECONDS` / `JEV_MIN_CONFIDENCE` | Budget + seuil gate |
| `AI_DECISION_TIMEOUT_SECONDS` | Budget total filtre |
| `EVENT_RADAR_ENABLED` | Master switch |
| `EVENT_RADAR_JEV_MIN_CONFIDENCE` | Seuil radar |
| `EVENT_RADAR_NEWS_LOOKBACK_DAYS` / `EVENT_RADAR_MAX_EVENTS` | Fraîcheur / cap |
| `EVENT_RADAR_CRYPTO_RSS_ENABLED` / `YAHOO_FINANCE_RSS` / `SEC_EDGAR` | Sources |
| `ENABLE_REFLECTION_WORKER` | Validation outcomes |
| `AI_CALIBRATION_MARKETS` / `LOOKBACK_DAYS` / `MIN_SAMPLES` | Calib offline |
| `ENABLE_CONFIDENCE_CALIBRATION` / `ENABLE_AI_ENSEMBLE` | Tuning avancé |
| `AGENT_LIVE_TRADING_ENABLED` | **Kill-switch (défaut false)** |
| `AGENT_DEFAULT_MAX_*_NOTIONAL` | Caps agent |

### Trading / paper (inspiration, pas copy live)

| Knob | Rôle |
|---|---|
| `ORDER_MODE` | Mode ordres |
| Protection / buffers spot | `SPOT_*`, pending worker |
| Strategy runtime shards/Kafka | Overkill IchiVol — ignorer V6 |

### Hors scope IchiVol

Billing Stripe/USDT, OAuth SaaS, multi-tenant `saas`, community marketplace, SMS Twilio branding legal.

---

## 4. Moteur — au-delà du gate Jev

| Module | Path | Récupérable |
|---|---|---|
| **Pre-trade gate 5 CHOICE** | `services/ai_decision_filter.py` | Oui → Guardian + pré-`paper_submit` |
| **Contexte PIT** | `services/ai_decision_context.py` | Oui → `eve/context.py` |
| **Event Radar** | `services/event_radar.py` | Oui → `engine/app/events/` |
| **ProtectionSpec** | `strategy_v2/protection.py` | Oui → paper protection |
| **Fee-aware trailing** | `utils/risk_guard.py` | Oui |
| **Virtual / signal-only accounts** | `virtual_trading.py`, `virtual_execution_costs.py` | Patterns coûts paper |
| **Calibration / reflection** | `ai_calibration.py`, `reflection.py` | Observe-only (pas auto-apply) |
| **Account risk / order budget** | `live_trading/account_risk.py`, `pending_orders/order_budget.py` | Inspiration Risk Kernel |
| **Agent Gateway + MCP** | `routes/agent_v1/`, `mcp_server/` | Scopes paper + confirms |
| Live brokers Alpaca/IBKR | `alpaca*`, `ibkr*` | **Non** |
| Billing crédits sur décisions | `_consume_credits` dans le filtre | **Non** |
| Fail-open si AI down (live) | même filtre | **Inverser** chez Ève → HOLD |

### Les 5 CHOICE du gate (rappel)

`data_quality` · `signal_alignment` · `market_regime` · `risk_check` · `execution_quality`  
→ règles code pass/reject ; exits / grid / DCA bypass.

---

## 5. Backlog récupération (corrigé)

| Prio | Item | Source QD | Cible IchiVol |
|---|---|---|---|
| **P0** | Gate 5 CHOICE paper-only + persist checks | `ai_decision_filter` + context | Guardian + `paper_submit` dry-run |
| **P0** | Settings schema knobs JEV/Radar (Basic/Advanced) | `routes/settings.py` | `SettingsPage` + `config.py` |
| **P1** | Event Radar instrument-scoped | `event_radar.py` | `events/` → `build_engine_context` |
| **P1** | Fallback ladder (JEV down → déterministe, **pas** OpenRouter System One) | flux Jev→LLM QD adapté | `eve/modes` + orchestrator |

### Appliqué 2026-10-16 (session locale)

| Item | Fichiers |
|---|---|
| Gate 5 CHOICE fail-closed | `eve/entry_gate.py`, orchestrator, paper_submit, panel |
| Settings schema Basic/Advanced | `eve/settings_schema.py`, `config.py`, API `/eve/settings/*`, `SettingsPage` onglet Ève/JEV, proxy PATCH |
| Knobs → policy + timeout adapter | `calibration.active_policy`, `jev/adapter._configured_timeout_s` |
| Event Radar instrument-scoped (P1) | `eve/event_radar.py` → `build_engine_context.event_radar`, API `/eve/event-radar/{symbol}` ; JEV puis rules (pas OpenRouter) |
| ProtectionSpec + fee-aware trail + coûts virtuels (P2) | `paper/protection_spec.py`, `stop_trail.trailing_exit_locks_net_profit`, `paper/virtual_execution_costs.py`, gate dans `protection.py` |
| Brier / ECE observe-only (P3) | `eve/calibration.py` + panel ; `applied: false`, pas d’auto-Platt |
| UI radar + timeline (P3) | `decision_time.event_radar` + badge panel ; timeline dossiers déjà en place |
| **P2** | ProtectionSpec unifié + fee-aware trail | `protection.py`, `risk_guard` | `paper/protection*` |
| **P2** | Coûts virtuels explicites | `virtual_execution_costs` | fees paper |
| **P3** | Calib Brier/ECE + reflection batch | `ai_calibration`, `reflection` | `eve/calibration` observe |
| **P3** | UI timeline décisions + radar dans Eve panel | `/ai-decisions`, `/event-radar` | `EveIntelligencePanel` |
| **P3** | MCP paper-only (optionnel) | `mcp_server` | plus tard |

---

## 6. Ne pas copier

- Brokers live, wallets, credentials encryption live  
- Billing / crédits / Stripe / USDT  
- Multi-tenant SaaS / community / referral  
- Fail-open live sur outage AI  
- Kafka hyperscale V6 / mobile H5  
- Ensemble multi-LLM comme System One  

---

*Audit local post-cloud — 2026-10-16. Remplace la lecture « gate only ».*
