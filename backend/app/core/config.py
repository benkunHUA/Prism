from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Aurora API"
    db_path: str = "data/aurora.db"
    # 部署时把前端构建产物挂到根路径；留空则只提供 API（本地开发用 Vite）
    static_dir: str = ""
    # 整站访问口令；auth_password 留空即关闭鉴权
    auth_user: str = "aurora"
    auth_password: str = ""

    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    # 输出预算：推理模型（如 deepseek-v4-flash）的 reasoning 也计入 max_tokens，需要留足余量
    llm_brief_max_tokens: int = 3000
    llm_daily_max_tokens: int = 12000
    llm_extract_max_tokens: int = 4000
    llm_translate_max_tokens: int = 3000
    # DeepSeek 推理模型（如 deepseek-v4-flash）默认会把预算消耗在 reasoning 上；
    # 采集/简报类任务不需要思维链，默认关闭。设为 auto 则交回模型决定。
    llm_thinking: str = "disabled"

    collect_cron: str = "0 */4 * * *"
    daily_analysis_hhmm: str = "08:00"
    scheduler_enabled: bool = True

    request_timeout_s: float = 20.0
    collect_concurrency: int = 4
    max_articles_per_source: int = 20
    max_content_chars: int = 8000
    max_analysis_input_chars: int = 6000
    top_articles_per_analysis: int = 30
    extract_enabled: bool = True
    # 译文（标题 + 摘要）在采集落库阶段生成；批量调用，一批多少篇
    translate_enabled: bool = True
    translate_batch_size: int = 10
    market_provider: str = "eastmoney"
    # 格式 "类别|名称=代码"，逗号分隔；eastmoney 用 secid，stooq 用其符号。
    # 类别取值与前端 ASSET_CLASSES 对齐：index/rate/fx/commodity/volatility/crypto/equity
    # 例："index|美元指数=100.UDI,rate|美债10年期收益率=171.US10Y"
    market_symbols: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
