from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:root@127.0.0.1:5432/ichivol_engine_dev"
    engine_api_prefix: str = "/api/engine"
    log_level: str = "info"
    # Phase 1b multi-actifs — empty = Twelve Data adapter not usable yet
    twelve_data_api_key: str = ""


settings = Settings()
