import os

from app.core.config import Settings


def test_defaults():
    os.environ.pop("DB_PATH", None)
    s = Settings(_env_file=None)
    assert s.db_path == "data/aurora.db"
    assert s.llm_provider == "deepseek"
    assert s.collect_cron == "0 */4 * * *"
    assert s.daily_analysis_hhmm == "08:00"
    assert s.extract_enabled is True
    assert s.market_provider == "eastmoney"
    assert s.market_symbols == ""


def test_env_override():
    s = Settings(_env_file=None, db_path=":memory:", llm_provider="openai")
    assert s.db_path == ":memory:"
    assert s.llm_provider == "openai"
