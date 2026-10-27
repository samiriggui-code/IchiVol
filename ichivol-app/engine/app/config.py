from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Push .env into os.environ so adapters that use os.getenv (JEV / TypeSafe) see keys.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:root@127.0.0.1:5432/ichivol_engine_dev"
    engine_api_prefix: str = "/api/engine"
    log_level: str = "info"
    # Phase 1b multi-actifs — empty = Twelve Data adapter not usable yet
    twelve_data_api_key: str = ""
    # Automated backtest evidence collection (CDC "condition 1" live-broker
    # gate) -- 40 full backtests/cycle is real load; enabled by default for
    # prod/VPS, disable locally (ENABLE_BACKTEST_EVIDENCE=false in .env) to
    # avoid re-running the whole cycle on every `--reload` dev restart.
    enable_backtest_evidence: bool = True
    backtest_evidence_interval_s: float = 86400.0
    # PaperBroker Phase 1 defaults (also frozen in strategy_profiles)
    paper_initial_cash_eur: float = 5000.0
    paper_risk_pct: float = 0.01
    paper_take_profit_r: float = 2.0
    paper_max_open_positions: int = 5
    # Signal tracking (evidence circuit): record every directional signal on each
    # screener scan, then measure what happened after it.
    enable_signal_tracking: bool = True
    signal_outcome_interval_s: float = 900.0
    # Decide on CLOSED candles only: a signal computed on the still-forming bar
    # can flip BUY <-> NO_TRADE within seconds (see propose -> confirm 422).
    # Entry price stays the live last price. Set false to restore the old behaviour.
    decide_on_closed_candles: bool = True
    # Stops/targets are watched every protection_interval_s independent of signals.
    enable_protection_monitor: bool = True
    protection_interval_s: float = 60.0
    # Flux direct Binance (WebSocket public, aucune clé) : stops / objectifs temps réel des lots crypto du compte
    # unique (app/paper/live_service.py). Désactivé par défaut (tests, dev) ; activé en prod par le compose.
    enable_live_feed: bool = False
    live_feed_ws_base: str = "wss://data-stream.binance.vision"
    live_feed_rest_base: str = "https://data-api.binance.vision"
    live_feed_stale_s: float = 10.0  # aucun message depuis N s -> « dégradé », reconnexion + relevés REST
    live_feed_rest_poll_s: float = 5.0  # cadence des relevés REST pendant la dégradation
    live_feed_refresh_s: float = 5.0  # relecture des lots ouverts surveillés
    # RS-D1 paper live (docs/RS-09-RS-D1-PAPER-DESIGN.md): separate portfolio RS_D1_PAPER_V1, rules = rs/book.py.
    # 2026-10-27 : coupé par défaut (portefeuille unique). Son livre (rs/book.py) tient sa propre caisse et ne
    # peut pas partager le compte ICHIVOL_MAIN_V1 sans adaptation ; le code et les backtests RS restent.
    enable_rs_d1_paper: bool = False
    rs_d1_interval_s: float = 60.0
    # OB-1 order book collector output (separate service, shared volume mounted read-only here).
    ob_data_dir: str = "/data/orderbook"
    # Eve V2 paper path — Risk Kernel submission. Default OFF (observation / dry-run only).
    # When true, LONG/SHORT potential verdicts may open on *existing* paper portfolios.
    # Never live brokers — paper portfolios only (QuantDinger AGENT_LIVE analogue).
    eve_paper_autonomy: bool = False
    # Autopilot: at most this many symbols judged by Ève per screener cycle (bounds JEV calls / credit).
    eve_autopilot_max_symbols: int = 8

    # --- Ève / JEV / Event Radar (QuantDinger Settings schema knobs) ---
    # Secrets (JEV_API_KEY / TYPESAFE_API_KEY) stay env-only via jev/providers.
    # jevos-v4 (local fallback) answers in ~14 s on the VPS: 5 s made every fallback call time out.
    jev_timeout_seconds: float = 30.0
    jev_min_confidence: float = 0.45
    eve_entry_gate_min_confidence: float = 0.55
    event_radar_enabled: bool = False
    event_radar_jev_min_confidence: float = 0.65
    event_radar_news_lookback_days: int = 2
    event_radar_max_events: int = 8
    event_radar_crypto_rss_enabled: bool = True
    event_radar_yahoo_finance_rss_enabled: bool = True
    event_radar_sec_edgar_enabled: bool = False


settings = Settings()
