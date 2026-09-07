from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Aurora API"
    db_path: str = "data/aurora.db"

    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"

    collect_cron: str = "0 */4 * * *"
    daily_analysis_hhmm: str = "08:00"
    scheduler_enabled: bool = True

    request_timeout_s: float = 20.0
    collect_concurrency: int = 4
    max_articles_per_source: int = 20
    max_content_chars: int = 8000
    max_analysis_input_chars: int = 6000
    top_articles_per_analysis: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
