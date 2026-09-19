from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # MT5 bridge (Phase 2, READ ONLY) -- unregistered unless explicitly
    # turned on (docs/TRADING_ARCHITECTURE_V2.md §11 rule: MT5 is a data
    # source/lab, never a dependency the engine needs to boot). The bridge
    # itself is a separate service (ichivol-app/mt5-bridge/) since the
    # MetaTrader5 python package only runs under Windows/Wine, never in
    # this engine's own Linux container.
    mt5_enabled: bool = False
    mt5_mode: str = "READ_ONLY"  # READ_ONLY | PAPER | DEMO -- LIVE never wired here
    mt5_bridge_url: str = "http://mt5-bridge:8000"
    mt5_timeout_s: float = 10.0


settings = Settings()
