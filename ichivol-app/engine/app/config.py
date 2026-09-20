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
    # Signal tracking (evidence circuit): record every directional signal on each
    # screener scan, then measure what happened after it.
    enable_signal_tracking: bool = True
    signal_outcome_interval_s: float = 900.0


settings = Settings()
