# Aurora 后端实施计划（采集 + 分析 + 调度 + API）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 Aurora 的完整 Python 后端：白名单源采集、去重入库、LLM 快讯/每日分析生成、定时调度与 REST API，全部经 pytest 验证。

**Architecture:** 单进程 FastAPI 应用：SQLAlchemy + SQLite(WAL) 做存储；repositories 隔离数据访问；services 层承载采集、分析与调度；APScheduler 内嵌于应用进程；前端（另一份计划）只通过 `/api/*` 交互。

**Tech Stack:** Python 3.12 + uv、FastAPI、SQLAlchemy 2、APScheduler、httpx、feedparser、trafilatura、beautifulsoup4、pytest。

---

## 文件结构（本计划创建）

```
backend/
  pyproject.toml
  .env.example
  data/seed_sources.json
  app/
    __init__.py
    main.py                 # app 工厂 + lifespan（建表/种子/启动调度）
    core/__init__.py
    core/config.py          # Settings（.env 读取）
    core/database.py        # engine/session/Base + WAL pragma
    core/constants.py       # 板块枚举与默认任务
    models/__init__.py      # 导出 ORM
    models/entities.py      # 8 张表
    repositories/__init__.py
    repositories/sources.py
    repositories/articles.py
    repositories/analyses.py
    repositories/tasks.py
    repositories/logs.py
    services/__init__.py
    services/seed.py        # 内置源与默认任务种子
    services/urlutil.py     # URL/标题规范化与哈希（纯函数）
    services/collector.py   # RSS/网页抓取、清洗、去重、入库
    services/llm.py         # ChatProvider 协议 + DeepSeek/OpenAI
    services/analyzer.py    # 快讯与每日分析生成、引用落库
    services/flow.py        # run_task_flow：任务→日志→分派
    services/scheduler.py   # APScheduler 同步/启停/防重入
    api/__init__.py
    api/deps.py             # get_db / settings 依赖
    api/routes_health.py
    api/routes_dashboard.py
    api/routes_categories.py
    api/routes_sources.py
    api/routes_articles.py
    api/routes_analyses.py
    api/routes_tasks.py
    api/routes_logs.py
  tests/
    conftest.py
    test_config.py
    test_database.py
    test_models.py
    test_urlutil.py
    test_collector.py
    test_llm.py
    test_analyzer.py
    test_flow.py
    test_scheduler.py
    test_repositories.py
    test_api_sources.py
    test_api_content.py
    test_api_tasks.py
```

下一份计划（B：前端）在 A 完成后编写，覆盖仪表盘/板块/阅读/源管理/任务管理五个页面与收尾。

---

### Task 0: 初始化后端工程

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`, `backend/app/models/__init__.py`, `backend/app/repositories/__init__.py`, `backend/app/services/__init__.py`, `backend/app/api/__init__.py`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "aurora-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlalchemy>=2.0",
  "apscheduler>=3.10,<4",
  "httpx>=0.27",
  "feedparser>=6.0",
  "trafilatura>=1.8",
  "beautifulsoup4>=4.12",
  "pydantic-settings>=2.4",
]

[dependency-groups]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: 创建 .env.example**

```dotenv
# LLM
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# 数据库与调度
DB_PATH=data/aurora.db
COLLECT_CRON=0 */4 * * *
DAILY_ANALYSIS_HHMM=08:00
SCHEDULER_ENABLED=true

# 采集参数
REQUEST_TIMEOUT_S=20
COLLECT_CONCURRENCY=4
MAX_ARTICLES_PER_SOURCE=20
MAX_CONTENT_CHARS=8000
MAX_ANALYSIS_INPUT_CHARS=6000
TOP_ARTICLES_PER_ANALYSIS=30
```

- [ ] **Step 3: 创建空包文件并安装依赖**

```bash
mkdir -p backend/app/core backend/app/models backend/app/repositories backend/app/services backend/app/api backend/tests backend/data
touch backend/app/__init__.py backend/app/core/__init__.py backend/app/models/__init__.py backend/app/repositories/__init__.py backend/app/services/__init__.py backend/app/api/__init__.py
cd backend && uv sync
```

Expected: 依赖安装成功，出现 `backend/.venv`。

- [ ] **Step 4: 提交**

```bash
git add backend
git commit -m "feat(backend): 工程骨架与依赖"
```

---

### Task 1: 配置 Settings

**Files:**
- Create: `backend/app/core/config.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: 写失败测试**

```python
import os

from app.core.config import Settings


def test_defaults():
    os.environ.pop("DB_PATH", None)
    s = Settings(_env_file=None)
    assert s.db_path == "data/aurora.db"
    assert s.llm_provider == "deepseek"
    assert s.collect_cron == "0 */4 * * *"
    assert s.daily_analysis_hhmm == "08:00"


def test_env_override():
    s = Settings(_env_file=None, db_path=":memory:", llm_provider="openai")
    assert s.db_path == ":memory:"
    assert s.llm_provider == "openai"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_config.py -q`
Expected: FAIL（`ModuleNotFoundError: app.core.config`）。

- [ ] **Step 3: 实现 config.py**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Aurora API"
    db_path: str = "data/aurora.db"

    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
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
```

- [ ] **Step 4: 运行通过**

Run: `cd backend && uv run pytest tests/test_config.py -q`
Expected: 2 passed。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat(backend): Settings 配置"
```

---

### Task 2: 数据库引擎与 WAL

**Files:**
- Create: `backend/app/core/database.py`
- Test: `backend/tests/test_database.py`

- [ ] **Step 1: 写失败测试**

```python
from sqlalchemy import text

from app.core.database import Base, make_engine, make_session_factory


def test_wal_and_foreign_keys(tmp_path):
    db_file = tmp_path / "t.db"
    engine = make_engine(str(db_file))
    with engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        fk = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert mode == "wal"
        assert fk == 1
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        assert session.execute(text("SELECT 1")).scalar() == 1
    engine.dispose()


def test_memory_engine():
    engine = make_engine(":memory:")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1
    engine.dispose()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_database.py -q`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现 database.py**

```python
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(db_path: str) -> Engine:
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{db_path}"
    else:
        url = "sqlite://"
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
```

- [ ] **Step 4: 运行通过**

Run: `cd backend && uv run pytest tests/test_database.py -q`
Expected: 2 passed。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat(backend): 数据库引擎与 WAL"
```

---

### Task 3: ORM 模型（八张表）

**Files:**
- Create: `backend/app/models/entities.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: 写失败测试**

```python
from app.core.database import Base, make_engine, make_session_factory
from app.models.entities import Article, Category, Source, SourceCategory


def _engine(tmp_path):
    engine = make_engine(str(tmp_path / "t.db"))
    Base.metadata.create_all(engine)
    return engine


def test_source_categories_and_article(tmp_path):
    engine = _engine(tmp_path)
    factory = make_session_factory(engine)
    with factory() as db:
        src = Source(name="Reuters", url="https://example.com/feed", feed_type="rss")
        src.source_categories = [
            SourceCategory(category=Category.economy.value),
            SourceCategory(category=Category.finance.value),
        ]
        db.add(src)
        db.flush()
        art = Article(source_id=src.id, category=Category.economy.value, url="https://example.com/a/1",
                      title="T", dedupe_hash="h1")
        db.add(art)
        db.commit()
        assert src.id and art.id


def test_delete_source_keeps_article_with_null_source(tmp_path):
    engine = _engine(tmp_path)
    factory = make_session_factory(engine)
    with factory() as db:
        src = Source(name="S", url="https://example.com/s", feed_type="rss")
        db.add(src)
        db.flush()
        art = Article(source_id=src.id, category=Category.politics.value, url="https://example.com/s/a",
                      title="T", dedupe_hash="h2")
        db.add(art)
        db.commit()
        db.delete(src)
        db.commit()
        assert db.get(Article, art.id).source_id is None
    engine.dispose()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_models.py -q`
Expected: FAIL（实体模块不存在）。

- [ ] **Step 3: 实现 entities.py**

```python
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Category(str, enum.Enum):
    politics = "politics"
    economy = "economy"
    finance = "finance"
    military = "military"


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(2000), unique=True)
    feed_type: Mapped[str] = mapped_column(String(10), default="rss")
    lang: Mapped[str] = mapped_column(String(10), default="en")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    source_categories: Mapped[list[SourceCategory]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    articles: Mapped[list[Article]] = relationship(back_populates="source")


class SourceCategory(Base):
    __tablename__ = "source_categories"
    __table_args__ = (UniqueConstraint("source_id", "category", name="uq_source_category"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(20))
    source: Mapped[Source] = relationship(back_populates="source_categories")


class Article(Base):
    __tablename__ = "articles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(20), index=True)
    url: Mapped[str] = mapped_column(String(2000), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text, default="")
    content_text: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    dedupe_hash: Mapped[str] = mapped_column(String(64), index=True)
    lang: Mapped[str] = mapped_column(String(10), default="en")

    source: Mapped[Source | None] = relationship(back_populates="articles")
    analysis_links: Mapped[list[AnalysisArticle]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), index=True)  # brief | daily
    category: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    content_md: Mapped[str] = mapped_column(Text, default="")
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    model: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(10), default="success", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    article_links: Mapped[list[AnalysisArticle]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class AnalysisArticle(Base):
    __tablename__ = "analysis_articles"
    __table_args__ = (
        UniqueConstraint("analysis_id", "article_id", name="uq_analysis_article"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    analysis: Mapped[Analysis] = relationship(back_populates="article_links")
    article: Mapped[Article] = relationship(back_populates="analysis_links")


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), index=True)  # collect | analyze
    category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cron: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RunLog(Base):
    __tablename__ = "run_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="running")
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class KVSetting(Base):
    __tablename__ = "kv_settings"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
```

- [ ] **Step 4: 导出实体**

```python
# backend/app/models/__init__.py
from app.models.entities import (  # noqa: F401
    Analysis,
    AnalysisArticle,
    Article,
    Category,
    KVSetting,
    RunLog,
    Source,
    SourceCategory,
    Task,
    utcnow,
)
```

- [ ] **Step 5: 运行通过**

Run: `cd backend && uv run pytest tests/test_models.py -q`
Expected: 2 passed。

- [ ] **Step 6: 提交**

```bash
git add backend
git commit -m "feat(backend): ORM 模型"
```

---

### Task 4: 内置源与默认任务种子

**Files:**
- Create: `backend/data/seed_sources.json`
- Create: `backend/app/core/constants.py`
- Create: `backend/app/services/seed.py`
- Test: `backend/tests/test_models.py`（沿用）后追加独立种子测试 `backend/tests/test_repositories.py` 中

- [ ] **Step 1: 创建 constants.py**

```python
from app.models.entities import Category

ALL_CATEGORIES = [c.value for c in Category]
```

- [ ] **Step 2: 创建 seed_sources.json**

```json
[
  {"name": "白宫新闻室", "url": "https://www.whitehouse.gov/feed/", "feed_type": "rss", "lang": "en", "categories": ["politics"]},
  {"name": "美国国务院新闻", "url": "https://www.state.gov/feed/", "feed_type": "rss", "lang": "en", "categories": ["politics"]},
  {"name": "BBC 世界新闻", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "feed_type": "rss", "lang": "en", "categories": ["politics", "economy"]},
  {"name": "英国外交部 GOV.UK", "url": "https://www.gov.uk/government/organisations/foreign-commonwealth-development-office.atom", "feed_type": "rss", "lang": "en", "categories": ["politics"]},
  {"name": "美联储新闻发布", "url": "https://www.federalreserve.gov/feeds/press_all.xml", "feed_type": "rss", "lang": "en", "categories": ["finance", "economy"]},
  {"name": "美国能源信息署 EIA", "url": "https://www.eia.gov/rss/press_rss.xml", "feed_type": "rss", "lang": "en", "categories": ["economy", "finance"]},
  {"name": "英格兰银行新闻", "url": "https://www.bankofengland.co.uk/rss/news", "feed_type": "rss", "lang": "en", "categories": ["economy", "finance"]},
  {"name": "美国国防部新闻", "url": "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=945&max=20", "feed_type": "rss", "lang": "en", "categories": ["military"]},
  {"name": "英国国防部 GOV.UK", "url": "https://www.gov.uk/government/organisations/ministry-of-defence.atom", "feed_type": "rss", "lang": "en", "categories": ["military"]},
  {"name": "世界银行新闻", "url": "https://www.worldbank.org/en/news/all?format=feed", "feed_type": "rss", "lang": "en", "categories": ["economy"]}
]
```

说明：种子源 URL 需在 M2 验收时用“测试抓取”验证；失效源会按健康规则自动停用，用户可随时在界面替换。

- [ ] **Step 3: 实现 seed.py**

```python
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import Source, SourceCategory, Task
from app.repositories.sources import create_source
from app.repositories.tasks import create_task

SEED_FILE = Path(__file__).resolve().parents[2] / "data" / "seed_sources.json"


def _cron_from_hhmm(hhmm: str) -> str:
    hour, minute = hhmm.split(":")
    return f"{minute} {hour} * * *"


def seed_defaults(db: Session, settings: Settings | None = None) -> bool:
    """空库时写入内置源与默认任务；返回是否执行了种子写入。"""
    if db.query(Source).first():
        return False
    settings = settings or Settings(_env_file=None)
    with SEED_FILE.open(encoding="utf-8") as fh:
        seeds = json.load(fh)
    for item in seeds:
        create_source(
            db,
            name=item["name"],
            url=item["url"],
            feed_type=item.get("feed_type", "rss"),
            lang=item.get("lang", "en"),
            categories=item["categories"],
        )
    create_task(db, name="采集·全板块", kind="collect", category=None, cron=settings.collect_cron)
    create_task(
        db,
        name="每日分析·四板块",
        kind="analyze",
        category=None,
        cron=_cron_from_hhmm(settings.daily_analysis_hhmm),
    )
    db.commit()
    return True
```

- [ ] **Step 4: 验证种子可运行**

Run: `cd backend && uv run python -c "from app.core.database import make_engine,make_session_factory,Base; from app.services.seed import seed_defaults; e=make_engine(':memory:'); Base.metadata.create_all(e); f=make_session_factory(e); db=f(); print(seed_defaults(db)); db.close(); e.dispose()"`
Expected: `True`（含后续仓储实现后执行）。该命令同时验证 seed 与仓储接口一致。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat(backend): 内置源与默认任务种子"
```

---

### Task 5: URL/标题规范化与去重哈希

**Files:**
- Create: `backend/app/services/urlutil.py`
- Test: `backend/tests/test_urlutil.py`

- [ ] **Step 1: 写失败测试**

```python
from app.services.urlutil import dedupe_hash, normalize_title, normalize_url


def test_normalize_url_strips_tracking_and_fragment():
    assert normalize_url("HTTPS://Example.com/Path/?utm_source=x&a=1#frag") == "https://example.com/path?a=1"


def test_normalize_title_strips_update_markers():
    assert normalize_title("Update: Breaking  News  Now") == "breaking news now"


def test_dedupe_hash_stable():
    h1 = dedupe_hash("https://x.com/a/?utm_source=t", "Update: Fed Hikes Rates")
    h2 = dedupe_hash("https://x.com/a/", "Fed hikes rates")
    assert h1 == h2
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_urlutil.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现 urlutil.py**

```python
import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "spm", "from",
}
UPDATE_PREFIX = re.compile(
    r"^\s*(update|breaking|live|exclusive|新闻|快讯|更新)\s*[:：\-–—]?\s*", re.IGNORECASE
)
WS = re.compile(r"\s+")


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parts.path.rstrip("/") if parts.path not in ("", "/") else ""
    query = urlencode(
        sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in TRACKING_KEYS)
    )
    return urlunsplit((scheme, netloc, path, query, ""))


def normalize_title(title: str) -> str:
    title = UPDATE_PREFIX.sub("", title.strip())
    title = WS.sub(" ", title)
    return title.lower()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dedupe_hash(url: str, title: str) -> str:
    return _sha(f"{normalize_url(url)}|{normalize_title(title)}")
```

- [ ] **Step 4: 运行通过**

Run: `cd backend && uv run pytest tests/test_urlutil.py -q`
Expected: 3 passed。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat(backend): URL/标题规范化去重哈希"
```

---

### Task 6: 仓储层与测试夹具

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/app/repositories/sources.py`
- Create: `backend/app/repositories/articles.py`
- Create: `backend/app/repositories/analyses.py`
- Create: `backend/app/repositories/tasks.py`
- Create: `backend/app/repositories/logs.py`
- Test: `backend/tests/test_repositories.py`

- [ ] **Step 1: 创建 conftest.py（含后续 API 测试的 app 夹具）**

```python
import pytest


@pytest.fixture()
def db(tmp_path):
    from app.core.database import Base, make_engine, make_session_factory

    engine = make_engine(str(tmp_path / "t.db"))
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    session = factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    from fastapi.testclient import TestClient

    app = create_app()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()
```

- [ ] **Step 2: 写仓储失败测试**

```python
from app.models.entities import Analysis, Category, Source
from app.repositories import analyses, articles, logs, sources, tasks
from datetime import datetime, timezone


def _source(db) -> Source:
    return sources.create_source(
        db, name="S", url="https://example.com/rss", feed_type="rss", lang="en",
        categories=[Category.economy.value],
    )


def test_source_crud_and_health_degrade(db):
    src = _source(db)
    assert [c.category for c in src.source_categories] == ["economy"]
    sources.update_source(db, src, categories=["economy", "finance"])
    assert {c.category for c in src.source_categories} == {"economy", "finance"}
    for i in range(3):
        sources.set_source_health(db, src, ok=False, error=f"err{i}")
    db.refresh(src)
    assert src.enabled is False
    assert src.error_count == 3
    sources.set_source_health(db, src, ok=True)
    db.refresh(src)
    assert src.enabled is True and src.error_count == 0


def test_article_insert_dedupes(db):
    src = _source(db)
    items = [
        dict(source_id=src.id, category="economy", url="https://example.com/a?utm_source=x",
             title="Update: Fed Hikes Rates", summary="s", content_text="", published_at=None,
             lang="en", dedupe_hash="h1"),
        dict(source_id=src.id, category="economy", url="https://example.com/a",
             title="Fed hikes rates", summary="s2", content_text="", published_at=None,
             lang="en", dedupe_hash="h1"),
        dict(source_id=src.id, category="economy", url="https://example.com/b",
             title="New Item", summary="s3", content_text="", published_at=None,
             lang="en", dedupe_hash="h2"),
    ]
    assert articles.insert_articles(db, items) == 2
    assert articles.insert_articles(db, items) == 0
    assert len(articles.list_articles(db, category="economy")) == 2


def test_analysis_and_links(db):
    src = _source(db)
    articles.insert_articles(db, [dict(source_id=src.id, category="economy", url="https://example.com/x",
                                       title="X", summary="", content_text="", published_at=None,
                                       lang="en", dedupe_hash="hx")])
    art = articles.list_articles(db)[0]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    an = analyses.create_analysis(
        db, kind="daily", category="economy", title="T", content_md="# T",
        period_start=now, period_end=now, model="fake",
    )
    analyses.link_articles(db, an, [art.id])
    assert analyses.get_analysis(db, an.id).article_links[0].article_id == art.id
    assert analyses.latest_analysis(db, "economy", "daily").id == an.id


def test_tasks_and_logs(db):
    t = tasks.create_task(db, name="采集", kind="collect", category=None, cron="0 */4 * * *")
    tasks.set_task_run(db, t, ok=True)
    db.refresh(t)
    assert t.last_run_at is not None
    lg = logs.create_log(db, t.id)
    logs.finish_log(db, lg, status="success", fetched_count=3, new_count=2)
    db.refresh(lg)
    assert lg.status == "success" and lg.new_count == 2
    assert logs.list_logs(db, limit=5)[0].id == lg.id
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_repositories.py -q`
Expected: FAIL（模块不存在）。

- [ ] **Step 4: 实现五个仓储文件**

```python
# backend/app/repositories/sources.py
from sqlalchemy.orm import Session

from app.models.entities import Source, SourceCategory, utcnow


def list_sources(db: Session) -> list[Source]:
    return db.query(Source).order_by(Source.id).all()


def get_source(db: Session, source_id: int) -> Source | None:
    return db.get(Source, source_id)


def create_source(db: Session, *, name: str, url: str, feed_type: str,
                  lang: str, categories: list[str], enabled: bool = True) -> Source:
    source = Source(name=name, url=url, feed_type=feed_type, lang=lang, enabled=enabled)
    for cat in categories:
        source.source_categories.append(SourceCategory(category=cat))
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def update_source(db: Session, source: Source, *, name: str | None = None,
                  url: str | None = None, feed_type: str | None = None,
                  lang: str | None = None, enabled: bool | None = None,
                  categories: list[str] | None = None) -> Source:
    if name is not None:
        source.name = name
    if url is not None:
        source.url = url
    if feed_type is not None:
        source.feed_type = feed_type
    if lang is not None:
        source.lang = lang
    if enabled is not None:
        source.enabled = enabled
    if categories is not None:
        existing = {sc.category for sc in source.source_categories}
        for cat in set(categories) - existing:
            source.source_categories.append(SourceCategory(category=cat))
        for sc in list(source.source_categories):
            if sc.category not in categories:
                source.source_categories.remove(sc)
    db.commit()
    db.refresh(source)
    return source


def set_source_health(db: Session, source: Source, *, ok: bool,
                      error: str | None = None) -> None:
    if ok:
        source.last_ok_at = utcnow()
        source.error_count = 0
        source.last_error = None
    else:
        source.error_count += 1
        source.last_error = error
        if source.error_count >= 3:
            source.enabled = False
    db.commit()


def delete_source(db: Session, source: Source) -> None:
    db.delete(source)
    db.commit()
```

```python
# backend/app/repositories/articles.py
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import Article


def existing_hashes(db: Session, hashes: list[str]) -> set[str]:
    if not hashes:
        return set()
    rows = db.query(Article.dedupe_hash).filter(Article.dedupe_hash.in_(hashes)).all()
    return {row[0] for row in rows}


def insert_articles(db: Session, items: list[dict]) -> int:
    """items 去重后批量入库，返回新增条数。"""
    if not items:
        return 0
    seen = existing_hashes(db, [it["dedupe_hash"] for it in items])
    fresh = []
    for it in items:
        if it["dedupe_hash"] in seen:
            continue
        seen.add(it["dedupe_hash"])
        fresh.append(
            Article(
                source_id=it["source_id"],
                category=it["category"],
                url=it["url"],
                title=it["title"],
                summary=it.get("summary", ""),
                content_text=it.get("content_text", ""),
                published_at=it.get("published_at"),
                lang=it.get("lang", "en"),
                dedupe_hash=it["dedupe_hash"],
            )
        )
    if fresh:
        db.add_all(fresh)
        db.commit()
    return len(fresh)


def list_articles(db: Session, category: str | None = None,
                  limit: int = 30, offset: int = 0) -> list[Article]:
    query = db.query(Article)
    if category:
        query = query.filter(Article.category == category)
    return query.order_by(Article.fetched_at.desc()).offset(offset).limit(limit).all()


def get_article(db: Session, article_id: int) -> Article | None:
    return db.get(Article, article_id)


def articles_for_analysis(db: Session, category: str, since: datetime,
                          until: datetime, limit: int = 30) -> list[Article]:
    return (
        db.query(Article)
        .filter(Article.category == category)
        .filter(Article.fetched_at >= since, Article.fetched_at < until)
        .order_by(Article.fetched_at.desc())
        .limit(limit)
        .all()
    )


def count_new_since(db: Session, category: str, since: datetime) -> int:
    return (
        db.query(Article)
        .filter(Article.category == category, Article.fetched_at >= since)
        .count()
    )
```

```python
# backend/app/repositories/analyses.py
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import Analysis, AnalysisArticle


def list_analyses(db: Session, category: str | None = None,
                  kind: str | None = None, limit: int = 50) -> list[Analysis]:
    query = db.query(Analysis)
    if category:
        query = query.filter(Analysis.category == category)
    if kind:
        query = query.filter(Analysis.kind == kind)
    return query.order_by(Analysis.created_at.desc()).limit(limit).all()


def get_analysis(db: Session, analysis_id: int) -> Analysis | None:
    return db.get(Analysis, analysis_id)


def create_analysis(db: Session, *, kind: str, category: str, title: str,
                    content_md: str, period_start: datetime | None,
                    period_end: datetime | None, model: str,
                    status: str = "success", error: str | None = None) -> Analysis:
    analysis = Analysis(
        kind=kind, category=category, title=title, content_md=content_md,
        period_start=period_start, period_end=period_end, model=model,
        status=status, error=error,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def link_articles(db: Session, analysis: Analysis, article_ids: list[int]) -> None:
    for aid in dict.fromkeys(article_ids):
        analysis.article_links.append(AnalysisArticle(article_id=aid))
    db.commit()


def latest_analysis(db: Session, category: str, kind: str) -> Analysis | None:
    return (
        db.query(Analysis)
        .filter(Analysis.category == category, Analysis.kind == kind)
        .order_by(Analysis.created_at.desc())
        .first()
    )
```

```python
# backend/app/repositories/tasks.py
from sqlalchemy.orm import Session

from app.models.entities import Task, utcnow


def list_tasks(db: Session) -> list[Task]:
    return db.query(Task).order_by(Task.id).all()


def get_task(db: Session, task_id: int) -> Task | None:
    return db.get(Task, task_id)


def create_task(db: Session, *, name: str, kind: str,
                category: str | None, cron: str, enabled: bool = True) -> Task:
    task = Task(name=name, kind=kind, category=category, cron=cron, enabled=enabled)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task: Task, *, name: str | None = None,
                kind: str | None = None, category: str | None = None,
                cron: str | None = None, enabled: bool | None = None) -> Task:
    if name is not None:
        task.name = name
    if kind is not None:
        task.kind = kind
    if category is not None:
        task.category = category
    if cron is not None:
        task.cron = cron
    if enabled is not None:
        task.enabled = enabled
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task: Task) -> None:
    db.delete(task)
    db.commit()


def set_task_run(db: Session, task: Task, *, ok: bool) -> None:
    task.last_run_at = utcnow()
    db.commit()
```

```python
# backend/app/repositories/logs.py
from sqlalchemy.orm import Session

from app.models.entities import RunLog, utcnow


def create_log(db: Session, task_id: int | None) -> RunLog:
    log = RunLog(task_id=task_id)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def finish_log(db: Session, log: RunLog, *, status: str,
               fetched_count: int = 0, new_count: int = 0,
               error: str | None = None) -> None:
    log.status = status
    log.fetched_count = fetched_count
    log.new_count = new_count
    log.error = error
    log.finished_at = utcnow()
    db.commit()


def list_logs(db: Session, limit: int = 50) -> list[RunLog]:
    return db.query(RunLog).order_by(RunLog.started_at.desc()).limit(limit).all()
```

- [ ] **Step 5: 运行通过**

Run: `cd backend && uv run pytest tests/test_repositories.py -q`
Expected: 4 passed。

- [ ] **Step 6: 提交**

```bash
git add backend
git commit -m "feat(backend): 仓储层"
```

---

### Task 7: 采集器（RSS/网页 + 清洗 + 去重入库）

**Files:**
- Create: `backend/app/services/collector.py`
- Create: `backend/tests/data/fixture_feed.xml`
- Modify: `backend/app/repositories/articles.py`（分类查询改为“按源所属板块”覆盖）
- Test: `backend/tests/test_collector.py`

- [ ] **Step 1: 先修正 articles.py 的分类查询**

将 `list_articles`、`articles_for_analysis`、`count_new_since` 三处实现替换为基于 `source_categories` 的覆盖查询：

```python
# backend/app/repositories/articles.py（完整文件替换）
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.entities import Article, SourceCategory


def _category_query(db: Session, category: str):
    """文章的 category 等于板块，或其来源挂载了该板块。"""
    return (
        db.query(Article)
        .join(SourceCategory, SourceCategory.source_id == Article.source_id, isouter=True)
        .filter(or_(Article.category == category, SourceCategory.category == category))
        .distinct()
    )


def existing_hashes(db: Session, hashes: list[str]) -> set[str]:
    if not hashes:
        return set()
    rows = db.query(Article.dedupe_hash).filter(Article.dedupe_hash.in_(hashes)).all()
    return {row[0] for row in rows}


def insert_articles(db: Session, items: list[dict]) -> int:
    if not items:
        return 0
    seen = existing_hashes(db, [it["dedupe_hash"] for it in items])
    fresh = []
    for it in items:
        if it["dedupe_hash"] in seen:
            continue
        seen.add(it["dedupe_hash"])
        fresh.append(
            Article(
                source_id=it["source_id"],
                category=it["category"],
                url=it["url"],
                title=it["title"],
                summary=it.get("summary", ""),
                content_text=it.get("content_text", ""),
                published_at=it.get("published_at"),
                lang=it.get("lang", "en"),
                dedupe_hash=it["dedupe_hash"],
            )
        )
    if fresh:
        db.add_all(fresh)
        db.commit()
    return len(fresh)


def list_articles(db: Session, category: str | None = None,
                  limit: int = 30, offset: int = 0) -> list[Article]:
    query = _category_query(db, category) if category else db.query(Article)
    return query.order_by(Article.fetched_at.desc()).offset(offset).limit(limit).all()


def get_article(db: Session, article_id: int) -> Article | None:
    return db.get(Article, article_id)


def articles_for_analysis(db: Session, category: str, since: datetime,
                          until: datetime, limit: int = 30) -> list[Article]:
    return (
        _category_query(db, category)
        .filter(Article.fetched_at >= since, Article.fetched_at < until)
        .order_by(Article.fetched_at.desc())
        .limit(limit)
        .all()
    )


def count_new_since(db: Session, category: str, since: datetime) -> int:
    return _category_query(db, category).filter(Article.fetched_at >= since).count()
```

- [ ] **Step 2: 创建 fixture RSS**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Fixture Feed</title>
    <item>
      <title>Update: Fed holds rates steady</title>
      <link>https://example.com/fed-1</link>
      <description>&lt;p&gt;The Federal Reserve kept its policy rate unchanged at 4.25 to 4.5 percent on Wednesday, citing continued resilience in the labor market, firm consumer spending, and a gradual easing of price pressures across the major sectors of the United States economy.&lt;/p&gt;</description>
      <pubDate>Mon, 07 Sep 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>ECB signals cautious path to lower rates</title>
      <link>https://example.com/ecb-1</link>
      <description>&lt;p&gt;European Central Bank policymakers signalled that any further reduction in borrowing costs would be gradual and data dependent, noting that underlying inflation remained above target while the euro area economy showed only modest growth momentum across the second half of the year.&lt;/p&gt;</description>
      <pubDate>Mon, 07 Sep 2026 11:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
```

- [ ] **Step 3: 写失败测试**

```python
from datetime import datetime, timezone

import httpx

from app.models.entities import Category, Source
from app.repositories import articles, sources
from app.services.collector import collect_new


def _mock_client(feed_path):
    feed = feed_path.read_bytes()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=feed)
    )
    return httpx.Client(transport=transport)


def test_collect_inserts_and_dedupes(db, tmp_path):
    feed = tmp_path / "feed.xml"
    feed.write_text((tmp_path.parent.parent / "data" / "fixture_feed.xml").read_text())
    src = sources.create_source(
        db, name="Fixture", url="https://example.com/rss", feed_type="rss", lang="en",
        categories=[Category.economy.value, Category.finance.value],
    )
    result = collect_new(db, client=_mock_client(feed))
    assert result["new"] == 2
    assert result["errors"] == []
    db.refresh(src)
    assert src.last_ok_at is not None and src.error_count == 0
    # 二次运行全部去重
    result2 = collect_new(db, client=_mock_client(feed))
    assert result2["new"] == 0
    # 经济板块能看到该源文章（多板块覆盖查询）
    assert len(articles.list_articles(db, category="economy")) == 2
    # 分析选材也命中
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    mats = articles.articles_for_analysis(db, "economy", now - __import__("datetime").timedelta(hours=1), now)
    assert len(mats) == 2


def test_collect_marks_failing_source(db):
    src = sources.create_source(
        db, name="Broken", url="https://example.com/broken", feed_type="rss", lang="en",
        categories=[Category.politics.value],
    )

    def _fail(request):  # noqa: ANN001
        raise httpx.ConnectError("boom", request=request)

    client = httpx.Client(transport=httpx.MockTransport(_fail))
    result = collect_new(db, client=client)
    assert result["errors"] and result["new"] == 0
    db.refresh(src)
    assert src.error_count == 1 and src.enabled is True
```

- [ ] **Step 4: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_collector.py -q`
Expected: FAIL（collector 模块不存在）。

- [ ] **Step 5: 实现 collector.py**

```python
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import time

import feedparser
import httpx
import trafilatura
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories import articles as articles_repo
from app.repositories import sources as sources_repo
from app.services.urlutil import dedupe_hash, normalize_url

USER_AGENT = "AuroraBot/0.1 (+personal research tool; polite fetcher)"


def _clean_html(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)


def _get_with_retry(client: httpx.Client, url: str, timeout: float, tries: int = 3) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(tries):
        try:
            resp = client.get(url, timeout=timeout, follow_redirects=True)
            resp.raise_for_status()
            return resp
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < tries - 1:
                time.sleep(2**attempt)
    if last_error:
        raise last_error
    raise RuntimeError("unreachable")


def _first_category(source) -> str:
    cats = [sc.category for sc in source.source_categories]
    return cats[0] if cats else "politics"


def _fetch_full_text(client: httpx.Client, url: str, timeout: float) -> tuple[str, str]:
    """返回 (标题, 正文)。失败时正文为空，不抛错。"""
    try:
        resp = client.get(url, timeout=timeout, follow_redirects=True)
        text = trafilatura.extract(resp.text) or ""
        meta = trafilatura.extract_metadata(resp.text)
        title = (meta.title if meta and meta.title else "").strip()
        return title, text
    except httpx.HTTPError:
        return "", ""


def fetch_source(source, settings: Settings, client: httpx.Client) -> tuple[list[dict], str | None]:
    """抓单个源，返回 (待入库条目, 错误消息)。"""
    try:
        resp = _get_with_retry(client, source.url, settings.request_timeout_s)
        items: list[dict] = []
        primary = _first_category(source)
        if source.feed_type == "rss":
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[: settings.max_articles_per_source]:
                url = normalize_url(entry.get("link", ""))
                title = (entry.get("title") or "").strip()
                if not url or not title:
                    continue
                summary = _clean_html(entry.get("summary", ""))
                content_text = summary
                if len(content_text) < 200:
                    _, content_text = _fetch_full_text(
                        client, url, min(15.0, settings.request_timeout_s)
                    )
                content_text = content_text[: settings.max_content_chars]
                published = None
                if entry.get("published_parsed"):
                    t = entry["published_parsed"]
                    published = datetime(t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)
                items.append(
                    {
                        "source_id": source.id,
                        "category": primary,
                        "url": url,
                        "title": title,
                        "summary": summary[:2000],
                        "content_text": content_text,
                        "published_at": published,
                        "lang": source.lang,
                        "dedupe_hash": dedupe_hash(url, title),
                    }
                )
        else:
            html = resp.text
            content_text = trafilatura.extract(html) or ""
            meta = trafilatura.extract_metadata(html)
            title = (meta.title if meta and meta.title else source.name).strip()
            items.append(
                {
                    "source_id": source.id,
                    "category": primary,
                    "url": normalize_url(source.url),
                    "title": title,
                    "summary": content_text[:2000],
                    "content_text": content_text[: settings.max_content_chars],
                    "published_at": None,
                    "lang": source.lang,
                    "dedupe_hash": dedupe_hash(source.url, title),
                }
            )
        return items, None
    except httpx.HTTPError as exc:
        return [], f"{type(exc).__name__}: {exc}"


def collect_new(db: Session, *, category: str | None = None,
                client: httpx.Client | None = None,
                settings: Settings | None = None) -> dict:
    settings = settings or Settings(_env_file=None)
    own_client = client is None
    client = client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=settings.request_timeout_s)
    try:
        sources = [
            s for s in sources_repo.list_sources(db)
            if s.enabled and (category is None or any(sc.category == category for sc in s.source_categories))
        ]
        results: dict[int, tuple[list[dict], str | None]] = {}
        with ThreadPoolExecutor(max_workers=settings.collect_concurrency) as pool:
            futures = {pool.submit(fetch_source, s, settings, client): s for s in sources}
            for fut in as_completed(futures):
                source = futures[fut]
                results[source.id] = fut.result()
        fetched = new = 0
        errors: list[str] = []
        for source in sources:
            items, error = results.get(source.id, ([], "source not fetched"))
            if error:
                errors.append(f"{source.name}: {error}")
                sources_repo.set_source_health(db, source, ok=False, error=error)
                continue
            fetched += len(items)
            new += articles_repo.insert_articles(db, items)
            sources_repo.set_source_health(db, source, ok=True)
        return {"fetched": fetched, "new": new, "errors": errors}
    finally:
        if own_client:
            client.close()
```

- [ ] **Step 6: 运行通过**

Run: `cd backend && uv run pytest tests/test_collector.py -q`
Expected: 2 passed。

- [ ] **Step 7: 提交**

```bash
git add backend
git commit -m "feat(backend): 采集器与去重入库"
```

---

### Task 8: LLM Provider 适配层

**Files:**
- Modify: `backend/app/core/config.py`（增加 openai_api_key）
- Modify: `backend/.env.example`
- Create: `backend/app/services/llm.py`
- Test: `backend/tests/test_llm.py`

- [ ] **Step 1: 增加 OpenAI Key 配置**

在 `Settings` 中 `deepseek_api_key: str = ""` 之后增加：

```python
    openai_api_key: str = ""
```

在 `.env.example` 中增加：

```dotenv
OPENAI_API_KEY=
```

- [ ] **Step 2: 写失败测试**

```python
import pytest

from app.core.config import Settings
from app.services.llm import ChatProvider, get_provider


class FakeProvider(ChatProvider):
    name = "fake"

    def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
        return "ok"


def test_fake_provider_contract():
    provider = FakeProvider(Settings(_env_file=None))
    assert provider.complete([{"role": "user", "content": "hi"}]) == "ok"


def test_factory_maps_deepseek():
    settings = Settings(_env_file=None, llm_provider="deepseek")
    assert get_provider(settings).name == "deepseek"


def test_missing_key_raises():
    from app.services.llm import DeepSeekProvider

    settings = Settings(_env_file=None, llm_provider="deepseek", deepseek_api_key="")
    provider = DeepSeekProvider(settings)
    with pytest.raises(RuntimeError, match="未配置"):
        provider.complete([{"role": "user", "content": "hi"}])
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_llm.py -q`
Expected: FAIL。

- [ ] **Step 4: 实现 llm.py**

```python
from __future__ import annotations

import time

import httpx

from app.core.config import Settings


class ChatProvider:
    name = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete(self, messages: list[dict], temperature: float = 0.2,
                 max_tokens: int = 4000) -> str:
        raise NotImplementedError


class _OpenAICompatProvider(ChatProvider):
    api_key_field = "deepseek_api_key"

    def complete(self, messages: list[dict], temperature: float = 0.2,
                 max_tokens: int = 4000) -> str:
        key = getattr(self.settings, self.api_key_field)
        if not key:
            raise RuntimeError(f"{self.api_key_field.upper()} 未配置")
        url = self.settings.llm_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {key}"}
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                resp = httpx.post(url, json=payload, headers=headers, timeout=120.0)
            except httpx.HTTPError as exc:
                last_error = exc
                time.sleep(2**attempt)
                continue
            if resp.status_code in (429, 500, 502, 503):
                last_error = RuntimeError(f"LLM HTTP {resp.status_code}: {resp.text[:200]}")
                time.sleep(2**attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        raise RuntimeError(f"LLM 调用失败: {last_error}")


class DeepSeekProvider(_OpenAICompatProvider):
    name = "deepseek"
    api_key_field = "deepseek_api_key"


class OpenAIProvider(_OpenAICompatProvider):
    name = "openai"
    api_key_field = "openai_api_key"


def get_provider(settings: Settings) -> ChatProvider:
    providers = {"deepseek": DeepSeekProvider, "openai": OpenAIProvider}
    cls = providers.get(settings.llm_provider)
    if cls is None:
        raise RuntimeError(f"未知 LLM provider: {settings.llm_provider}")
    return cls(settings)
```

- [ ] **Step 5: 运行通过**

Run: `cd backend && uv run pytest tests/test_llm.py -q`
Expected: 3 passed。

- [ ] **Step 6: 提交**

```bash
git add backend
git commit -m "feat(backend): LLM Provider 适配层"
```

---

### Task 9: 分析管道（快讯 + 每日文章）

**Files:**
- Create: `backend/app/services/analyzer.py`
- Test: `backend/tests/test_analyzer.py`

- [ ] **Step 1: 写失败测试**

```python
from datetime import datetime, timedelta, timezone

from app.models.entities import Category
from app.repositories import analyses, articles, sources
from app.services.analyzer import generate_brief, generate_daily
from app.services.llm import ChatProvider


class FakeProvider(ChatProvider):
    name = "fake"

    def __init__(self, settings, text: str):
        super().__init__(settings)
        self.text = text

    def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
        return self.text


def _seed_material(db):
    src = sources.create_source(
        db, name="S", url="https://example.com/rss", feed_type="rss", lang="en",
        categories=[Category.economy.value],
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    articles.insert_articles(db, [
        dict(source_id=src.id, category="economy", url="https://example.com/a",
             title="Fed moves", summary="summary a", content_text="long body a" * 50,
             published_at=now, lang="en", dedupe_hash="ha"),
        dict(source_id=src.id, category="economy", url="https://example.com/b",
             title="ECB moves", summary="summary b", content_text="long body b" * 50,
             published_at=now, lang="en", dedupe_hash="hb"),
    ])
    return now


def test_generate_brief_stores_markdown(db):
    from app.core.config import Settings

    now = _seed_material(db)
    settings = Settings(_env_file=None)
    provider = FakeProvider(settings, "- **事件**：Fed moves\n  **影响**：中\n  **来源**：S")
    result = generate_brief(db, "economy", provider, settings, since=now - timedelta(hours=1))
    assert result is not None and result.kind == "brief"
    assert "Fed moves" in result.content_md


def test_generate_daily_links_only_real_citations(db):
    from app.core.config import Settings

    now = _seed_material(db)
    settings = Settings(_env_file=None)
    md = (
        "## 要点速览\n- 关键结论一\n\n## 重大事件与事实\n事件描述\n\n"
        "## 资料来源\n- 1 S · Fed moves\n- 2 S · ECB moves\n- 9 Fake · Not real"
    )
    provider = FakeProvider(settings, md)
    result = generate_daily(db, "economy", provider, settings, until=now + timedelta(seconds=5))
    assert result is not None and result.kind == "daily"
    assert result.status == "success"
    linked = {link.article_id for link in analyses.get_analysis(db, result.id).article_links}
    material_ids = {a.id for a in articles.articles_for_analysis(db, "economy", now - timedelta(hours=24), now + timedelta(seconds=5))}
    assert linked == material_ids and len(linked) == 2


def test_generate_daily_empty_returns_none(db):
    from app.core.config import Settings

    settings = Settings(_env_file=None)
    provider = FakeProvider(settings, "irrelevant")
    assert generate_daily(db, "military", provider, settings) is None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_analyzer.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现 analyzer.py**

```python
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import Analysis, Category
from app.repositories import analyses as analyses_repo
from app.repositories import articles as articles_repo
from app.services.llm import ChatProvider

CATEGORY_LABELS = {
    Category.politics.value: "政治",
    Category.economy.value: "经济",
    Category.finance.value: "金融",
    Category.military.value: "军事",
}
ALL = [c.value for c in Category]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _numbered_materials(articles, settings: Settings) -> str:
    lines = []
    for i, art in enumerate(articles, start=1):
        body = (art.summary or art.content_text or "")[: settings.max_analysis_input_chars]
        lines.append(
            f"[{i}] 站点:{art.source.name if art.source else 'unknown'} | 时间:{art.fetched_at:%Y-%m-%d %H:%M} | "
            f"标题:{art.title}\n正文:{body}"
        )
    return "\n\n".join(lines)


def _parse_citation_ids(content_md: str, max_id: int) -> list[int]:
    section = content_md.rsplit("资料来源", 1)[-1]
    ids = []
    for line in section.splitlines():
        m = re.match(r"^\s*[-*]?\s*(\d+)[.、)）]?\s*", line)
        if not m:
            continue
        n = int(m.group(1))
        if 1 <= n <= max_id and n not in ids:
            ids.append(n)
    return ids


def generate_brief(db: Session, category: str, provider: ChatProvider,
                   settings: Settings, *, since: datetime | None = None) -> Analysis | None:
    until = _now()
    since = since or (until - timedelta(hours=6))
    materials = articles_repo.articles_for_analysis(
        db, category, since, until, limit=settings.top_articles_per_analysis
    )
    if not materials:
        return None
    prompt = (
        f"你是面向投资与研究的板块简报助手。基于以下 {len(materials)} 条材料（编号 [n] 对应材料），"
        f"用中文写 {category} 板块快讯要点，3~5 条。每条格式：\n"
        "**事件：**一句话\n**影响：**对市场/政策/局势的提示\n**来源：**站点名称\n"
        "只能基于给定材料，禁止编造。\n\n材料：\n" + _numbered_materials(materials, settings)
    )
    content = provider.complete(
        [{"role": "user", "content": prompt}], temperature=0.2, max_tokens=2000
    )
    return analyses_repo.create_analysis(
        db, kind="brief", category=category,
        title=f"{CATEGORY_LABELS.get(category, category)}快讯 {until:%H:%M}",
        content_md=content, period_start=since, period_end=until,
        model=settings.llm_model,
    )


def generate_daily(db: Session, category: str, provider: ChatProvider,
                   settings: Settings, *, until: datetime | None = None) -> Analysis | None:
    until = until or _now()
    since = until - timedelta(hours=24)
    materials = articles_repo.articles_for_analysis(
        db, category, since, until, limit=settings.top_articles_per_analysis
    )
    if not materials:
        return None
    prompt = (
        f"你是严谨的宏观研究与投资参考分析师。基于以下 {len(materials)} 条编号材料"
        f"（[n] 站点 | 时间 | 标题 | 正文），为「{CATEGORY_LABELS.get(category, category)}」板块"
        "写一篇 1500~2500 字中文分析，Markdown 格式，固定章节：\n"
        "## 要点速览\n## 重大事件与事实\n## 影响与传导分析\n## 风险与关注信号\n## 资料来源\n"
        "规则：只能引用给定材料；资料来源逐行写 `- 编号 站点 · 标题`；"
        "禁止编造来源、数据与机构表态。\n\n材料：\n" + _numbered_materials(materials, settings)
    )
    content = provider.complete(
        [{"role": "user", "content": prompt}], temperature=0.2, max_tokens=4000
    )
    analysis = analyses_repo.create_analysis(
        db, kind="daily", category=category,
        title=f"{CATEGORY_LABELS.get(category, category)}每日分析 {until:%Y-%m-%d}",
        content_md=content, period_start=since, period_end=until,
        model=settings.llm_model,
    )
    ids = _parse_citation_ids(content, len(materials))
    valid_ids = [materials[i - 1].id for i in ids if i <= len(materials)]
    if valid_ids:
        analyses_repo.link_articles(db, analysis, valid_ids)
    return analysis
```

- [ ] **Step 4: 运行通过**

Run: `cd backend && uv run pytest tests/test_analyzer.py -q`
Expected: 3 passed。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat(backend): 快讯与每日分析管道"
```

---

### Task 10: 任务执行流 run_task_flow

**Files:**
- Create: `backend/app/services/flow.py`
- Test: `backend/tests/test_flow.py`

- [ ] **Step 1: 写失败测试**

```python
from datetime import datetime, timedelta, timezone

from app.models.entities import Category, Source
from app.repositories import analyses, articles, logs, sources, tasks
from app.services.flow import run_task_flow
from app.services.llm import ChatProvider


class FakeProvider(ChatProvider):
    name = "fake"

    def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
        return "- **事件**：Fed moves\n  **影响**：关注利率路径\n  **来源**：Fixture"


def _feed_client(tmp_path):
    import httpx

    feed = (tmp_path.parent.parent / "data" / "fixture_feed.xml").read_bytes()
    return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=feed)))


def _setup(db, tmp_path):
    src = sources.create_source(
        db, name="Fixture", url="https://example.com/rss", feed_type="rss", lang="en",
        categories=[Category.economy.value, Category.finance.value],
    )
    task = tasks.create_task(db, name="采集", kind="collect", category=None, cron="0 */4 * * *")
    return src, task


def test_collect_flow_writes_log_and_brief(db, tmp_path):
    from app.core.config import Settings

    src, task = _setup(db, tmp_path)
    settings = Settings(_env_file=None)
    result = run_task_flow(
        db, task, client=_feed_client(tmp_path),
        provider=FakeProvider(settings), settings=settings,
    )
    assert result["status"] == "success"
    assert result["new"] == 2
    assert logs.list_logs(db)[0].status == "success"
    assert len(analyses.list_analyses(db, kind="brief")) == 2  # economy + finance 各有快讯


def test_analyze_flow_creates_daily(db, tmp_path):
    from app.core.config import Settings

    _setup(db, tmp_path)
    settings = Settings(_env_file=None)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    articles.insert_articles(db, [
        dict(source_id=None, category="economy", url="https://example.com/x",
             title="X", summary="s", content_text="c" * 500,
             published_at=now, lang="en", dedupe_hash="hx"),
    ])
    task = tasks.create_task(db, name="分析", kind="analyze", category="economy", cron="0 8 * * *")
    result = run_task_flow(db, task, provider=FakeProvider(settings), settings=settings)
    assert result["status"] == "success"
    daily = analyses.latest_analysis(db, "economy", "daily")
    assert daily is not None and daily.status == "success"


def test_failed_provider_marks_partial(db, tmp_path):
    from app.core.config import Settings

    class BoomProvider(FakeProvider):
        def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
            raise RuntimeError("boom")

    _setup(db, tmp_path)
    settings = Settings(_env_file=None)
    task = tasks.create_task(db, name="分析", kind="analyze", category="military", cron="0 8 * * *")
    result = run_task_flow(db, task, provider=BoomProvider(settings), settings=settings)
    assert result["status"] == "failed"
    assert "military" in " ".join(result["errors"])
    assert logs.list_logs(db)[0].status == "failed"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_flow.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现 flow.py**

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.constants import ALL_CATEGORIES
from app.models.entities import Task
from app.repositories import articles as articles_repo
from app.repositories import logs as logs_repo
from app.repositories import tasks as tasks_repo
from app.services import analyzer
from app.services.collector import collect_new
from app.services.llm import ChatProvider, get_provider


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _task_categories(task: Task) -> list[str]:
    return [task.category] if task.category else ALL_CATEGORIES


def run_task_flow(db: Session, task: Task, *, client=None,
                  provider: ChatProvider | None = None,
                  settings: Settings | None = None) -> dict:
    """执行单个任务，全程写 run_logs；返回状态摘要。"""
    settings = settings or Settings(_env_file=None)
    started = _utcnow()
    log = logs_repo.create_log(db, task.id)
    fetched = new = 0
    errors: list[str] = []
    status = "success"
    try:
        if task.kind == "collect":
            result = collect_new(db, category=task.category, client=client, settings=settings)
            fetched += result["fetched"]
            new += result["new"]
            errors.extend(result["errors"])
            brief_categories = _task_categories(task)
            prov = provider or get_provider(settings)
            since = started - timedelta(hours=6)
            for cat in brief_categories:
                if articles_repo.count_new_since(db, cat, since):
                    try:
                        analyzer.generate_brief(db, cat, prov, settings, since=since)
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"{cat} 快讯失败: {exc}")
        elif task.kind == "analyze":
            prov = provider or get_provider(settings)
            for cat in _task_categories(task):
                try:
                    analyzer.generate_daily(db, cat, prov, settings)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{cat} 每日分析失败: {exc}")
        else:
            raise ValueError(f"未知任务类型: {task.kind}")
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))
    status = "success" if not errors else ("partial" if new else "failed")
    error_msg = "；".join(errors)[:4000] or None
    logs_repo.finish_log(
        db, log, status=status, fetched_count=fetched, new_count=new, error=error_msg
    )
    tasks_repo.set_task_run(db, task, ok=status != "failed")
    return {"task_id": task.id, "status": status, "fetched": fetched, "new": new, "errors": errors}
```

- [ ] **Step 4: 运行通过**

Run: `cd backend && uv run pytest tests/test_flow.py -q`
Expected: 3 passed。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat(backend): 任务执行流与运行日志"
```

---

### Task 11: 调度器（APScheduler 同步/防重入）

**Files:**
- Create: `backend/app/services/scheduler.py`
- Test: `backend/tests/test_scheduler.py`

- [ ] **Step 1: 写失败测试**

```python
from app.core.config import Settings
from app.core.database import Base, make_engine, make_session_factory
from app.repositories import tasks as tasks_repo
from app.services.scheduler import SchedulerManager


def test_sync_registers_and_removes_jobs(tmp_path):
    engine = make_engine(str(tmp_path / "s.db"))
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as db:
        task = tasks_repo.create_task(db, name="年度", kind="collect", category=None, cron="0 0 1 1 *")
        task_id = task.id
    settings = Settings(_env_file=None, scheduler_enabled=True)
    mgr = SchedulerManager(factory, settings)
    mgr.start()
    try:
        job = mgr.scheduler.get_job(f"task-{task_id}")
        assert job is not None
        assert mgr.scheduler.get_job("sync-tasks") is not None
        with factory() as db:
            task = tasks_repo.get_task(db, task_id)
            tasks_repo.update_task(db, task, enabled=False)
        mgr.sync()
        assert mgr.scheduler.get_job(f"task-{task_id}") is None
    finally:
        mgr.shutdown()
        engine.dispose()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_scheduler.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现 scheduler.py**

```python
from __future__ import annotations

import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models.entities import Task
from app.repositories import tasks as tasks_repo
from app.services.flow import run_task_flow


class SchedulerManager:
    """启动后每分钟与 tasks 表同步；作业带进程内锁，防止手动/定时重入。"""

    def __init__(self, session_factory: sessionmaker, settings: Settings) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.scheduler = BackgroundScheduler(timezone="UTC")
        self._lock = threading.Lock()

    def start(self) -> None:
        self.scheduler.add_job(
            self.sync, "interval", minutes=1, id="sync-tasks",
            replace_existing=True, max_instances=1, coalesce=True,
        )
        self.scheduler.start()
        self.sync()

    def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)

    def sync(self) -> None:
        with self.session_factory() as db:
            tasks = tasks_repo.list_tasks(db)
            enabled = {t.id for t in tasks if t.enabled}
            for task in tasks:
                job_id = f"task-{task.id}"
                if task.id in enabled:
                    trigger = CronTrigger.from_crontab(task.cron, timezone="UTC")
                    self.scheduler.add_job(
                        self._guarded, trigger, args=[task.id],
                        id=job_id, replace_existing=True,
                        max_instances=1, coalesce=True,
                    )
                elif self.scheduler.get_job(job_id):
                    self.scheduler.remove_job(job_id)
            # 删除已不存在的任务对应作业
            for job in self.scheduler.get_jobs():
                if job.id.startswith("task-") and int(job.id.split("-", 1)[1]) not in enabled:
                    self.scheduler.remove_job(job.id)
            # 回写 next_run_at（去时区）
            for task in tasks:
                job = self.scheduler.get_job(f"task-{task.id}")
                if job and job.next_run_time:
                    task.next_run_at = job.next_run_time.replace(tzinfo=None)
            db.commit()

    def _guarded(self, task_id: int) -> None:
        with self._lock:
            with self.session_factory() as db:
                task: Task | None = tasks_repo.get_task(db, task_id)
                if task and task.enabled:
                    run_task_flow(db, task, settings=self.settings)
```

- [ ] **Step 4: 运行通过**

Run: `cd backend && uv run pytest tests/test_scheduler.py -q`
Expected: 1 passed。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat(backend): APScheduler 任务同步"
```

---

### Task 12: API 基础设施与源管理路由

**Files:**
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/routes_health.py`
- Modify: `backend/app/repositories/articles.py`（增加 count_all_since）
- Modify: `backend/app/repositories/analyses.py`（增加 count_daily_since）
- Create: `backend/app/api/routes_sources.py`
- Test: `backend/tests/test_api_sources.py`

- [ ] **Step 1: 增加两个计数仓储函数**

在 `articles.py` 末尾追加：

```python
def count_all_since(db: Session, since: datetime) -> int:
    return db.query(Article).filter(Article.fetched_at >= since).count()
```

在 `analyses.py` 末尾追加：

```python
def count_daily_since(db: Session, since: datetime) -> int:
    return (
        db.query(Analysis)
        .filter(Analysis.kind == "daily", Analysis.status == "success",
                Analysis.created_at >= since)
        .count()
    )
```

- [ ] **Step 2: 创建 deps.py 与健康检查**

```python
# backend/app/api/deps.py
from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session


def get_db(request: Request) -> Generator[Session, None, None]:
    factory = request.app.state.session_factory
    db: Session = factory()
    try:
        yield db
    finally:
        db.close()
```

```python
# backend/app/api/routes_health.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 3: 写源管理 API 失败测试**

```python
from app.models.entities import Category


def test_list_and_create_source(client):
    resp = client.get("/api/sources")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 10  # 种子源

    body = {
        "name": "Test Feed", "url": "https://test.example/feed",
        "feed_type": "rss", "lang": "en", "categories": ["finance"],
    }
    created = client.post("/api/sources", json=body)
    assert created.status_code == 201
    data = created.json()
    assert data["categories"] == ["finance"] and data["enabled"] is True

    dup = client.post("/api/sources", json=body)
    assert dup.status_code == 409


def test_patch_and_delete_source(client):
    source_id = client.get("/api/sources").json()["items"][0]["id"]
    resp = client.patch(f"/api/sources/{source_id}", json={"enabled": False, "categories": ["economy"]})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["categories"] == ["economy"]
    assert client.delete(f"/api/sources/{source_id}").status_code == 204
    assert client.get(f"/api/sources/{source_id}").status_code == 404


def test_source_test_endpoint(client, monkeypatch):
    from app.api import routes_sources

    def fake_fetch(source, settings, http):
        return (
            [{"url": "https://x.test/a", "title": "T", "published_at": None}],
            None,
        )

    monkeypatch.setattr(routes_sources, "fetch_source", fake_fetch)
    source_id = client.get("/api/sources").json()["items"][0]["id"]
    resp = client.post(f"/api/sources/{source_id}/test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True and body["preview"][0]["title"] == "T"
```

- [ ] **Step 4: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_api_sources.py -q`
Expected: FAIL（main/routes 不存在）。

- [ ] **Step 5: 实现 routes_sources.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from httpx import Client
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.entities import Source
from app.repositories import sources as repo
from app.services.collector import USER_AGENT, fetch_source

router = APIRouter(prefix="/api/sources", tags=["sources"])


class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=5, max_length=2000)
    feed_type: str = Field(default="rss", pattern="^(rss|page)$")
    lang: str = Field(default="en", max_length=10)
    enabled: bool = True
    categories: list[str] = Field(min_length=1)


class SourcePatch(BaseModel):
    name: str | None = None
    url: str | None = None
    feed_type: str | None = Field(default=None, pattern="^(rss|page)$")
    lang: str | None = None
    enabled: bool | None = None
    categories: list[str] | None = None


def _out(source: Source) -> dict:
    return {
        "id": source.id,
        "name": source.name,
        "url": source.url,
        "feed_type": source.feed_type,
        "lang": source.lang,
        "enabled": source.enabled,
        "categories": [sc.category for sc in source.source_categories],
        "last_ok_at": source.last_ok_at.isoformat() if source.last_ok_at else None,
        "last_error": source.last_error,
        "error_count": source.error_count,
    }


def _require_source(db: Session, source_id: int) -> Source:
    source = repo.get_source(db, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="采集源不存在")
    return source


@router.get("")
def list_sources(db: Session = Depends(get_db)) -> dict:
    return {"items": [_out(s) for s in repo.list_sources(db)]}


@router.get("/{source_id}")
def get_source(source_id: int, db: Session = Depends(get_db)) -> dict:
    return _out(_require_source(db, source_id))


@router.post("", status_code=201)
def create_source(payload: SourceIn, db: Session = Depends(get_db)) -> dict:
    try:
        source = repo.create_source(
            db, name=payload.name, url=payload.url, feed_type=payload.feed_type,
            lang=payload.lang, categories=payload.categories, enabled=payload.enabled,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该 URL 已存在") from None
    return _out(source)


@router.patch("/{source_id}")
def patch_source(source_id: int, payload: SourcePatch,
                 db: Session = Depends(get_db)) -> dict:
    source = _require_source(db, source_id)
    if payload.url:
        source.url = payload.url
    try:
        source = repo.update_source(
            db, source, name=payload.name, url=payload.url, feed_type=payload.feed_type,
            lang=payload.lang, enabled=payload.enabled, categories=payload.categories,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该 URL 已存在") from None
    return _out(source)


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)) -> None:
    repo.delete_source(db, _require_source(db, source_id))


@router.post("/{source_id}/test")
def test_source(source_id: int, db: Session = Depends(get_db)) -> dict:
    # 真实抓取一次，不入库，只返回前 3 条预览
    source = _require_source(db, source_id)
    try:
        from app.core.config import get_settings

        settings = get_settings()
        with Client(headers={"User-Agent": USER_AGENT}, timeout=settings.request_timeout_s) as http:
            items, error = fetch_source(source, settings, http)
        return {
            "ok": error is None,
            "error": error,
            "preview": [
                {"title": it["title"], "url": it["url"], "published_at": it.get("published_at")}
                for it in items[:3]
            ],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "preview": []}
```

- [ ] **Step 6: 运行通过**

Run: `cd backend && uv run pytest tests/test_api_sources.py -q`
Expected: 3 passed（需要 main.py 已注册源路由；若失败先完成 Task 15 的 app 装配再回跑本文件）。

- [ ] **Step 7: 提交**

```bash
git add backend
git commit -m "feat(backend): 源管理 API"
```

---

### Task 13: 内容路由（分类/文章/分析/仪表盘/日志）

**Files:**
- Create: `backend/app/api/routes_dashboard.py`
- Create: `backend/app/api/routes_categories.py`
- Create: `backend/app/api/routes_articles.py`
- Create: `backend/app/api/routes_analyses.py`
- Create: `backend/app/api/routes_logs.py`
- Test: `backend/tests/test_api_content.py`

- [ ] **Step 1: 写失败测试**

```python
from datetime import datetime, timezone

from app.models.entities import Category, Source
from app.repositories import analyses, articles, logs, sources, tasks


def _seed(client):
    with client.app.state.session_factory() as db:
        src = sources.create_source(
            db, name="S", url="https://example.com/rss", feed_type="rss", lang="en",
            categories=[Category.economy.value],
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        articles.insert_articles(db, [
            dict(source_id=src.id, category="economy", url="https://example.com/a",
                 title="Fed moves", summary="sum", content_text="body",
                 published_at=now, lang="en", dedupe_hash="ha"),
            dict(source_id=src.id, category="economy", url="https://example.com/b",
                 title="ECB moves", summary="sum", content_text="body",
                 published_at=now, lang="en", dedupe_hash="hb"),
        ])
        an = analyses.create_analysis(
            db, kind="daily", category="economy", title="经济每日分析",
            content_md="## 要点速览\n正文", period_start=now, period_end=now, model="fake",
        )
        ids = [a.id for a in articles.list_articles(db, category="economy")]
        analyses.link_articles(db, an, ids)
        task = tasks.create_task(db, name="采集", kind="collect", category=None, cron="0 */4 * * *")
        lg = logs.create_log(db, task.id)
        logs.finish_log(db, lg, status="success", fetched_count=2, new_count=2)
        return an.id


def test_content_endpoints(client):
    analysis_id = _seed(client)

    cats = client.get("/api/categories").json()
    economy = next(c for c in cats if c["category"] == "economy")
    assert economy["article_count"] >= 2

    art_resp = client.get("/api/categories/economy/articles?limit=10")
    assert art_resp.status_code == 200
    assert len(art_resp.json()["items"]) == 2

    detail = client.get(f"/api/analyses/{analysis_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["kind"] == "daily" and len(body["citations"]) == 2
    assert body["citations"][0]["url"].startswith("https://example.com/")

    dash = client.get("/api/dashboard/summary")
    assert dash.status_code == 200
    data = dash.json()
    assert data["today_articles"] >= 2 and data["today_analyses"] >= 1
    assert data["source_health"]["healthy"] >= 1
    assert data["next_run_at"] is not None

    logs_resp = client.get("/api/logs?limit=5")
    assert logs_resp.status_code == 200
    assert logs_resp.json()["items"][0]["status"] == "success"


def test_article_detail(client):
    _seed(client)
    article_id = client.get("/api/categories/economy/articles").json()["items"][0]["id"]
    body = client.get(f"/api/articles/{article_id}").json()
    assert body["title"] in ("Fed moves", "ECB moves")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_api_content.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现五个路由文件**

```python
# backend/app/api/routes_dashboard.py
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.constants import ALL_CATEGORIES
from app.models.entities import Source
from app.repositories import analyses as analyses_repo
from app.repositories import articles as articles_repo
from app.repositories import sources as sources_repo
from app.repositories import tasks as tasks_repo

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _today_start() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None).replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    since = _today_start()
    sources = sources_repo.list_sources(db)
    healthy = sum(1 for s in sources if s.enabled and s.error_count == 0)
    enabled = sum(1 for s in sources if s.enabled)
    next_run = min(
        (t.next_run_at for t in tasks_repo.list_tasks(db) if t.enabled and t.next_run_at),
        default=None,
    )
    return {
        "today_articles": articles_repo.count_all_since(db, since),
        "today_analyses": analyses_repo.count_daily_since(db, since),
        "source_health": {"healthy": healthy, "enabled": enabled},
        "next_run_at": next_run.isoformat() if next_run else None,
        "categories": ALL_CATEGORIES,
    }
```

```python
# backend/app/api/routes_categories.py
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.constants import ALL_CATEGORIES
from app.repositories import analyses as analyses_repo
from app.repositories import articles as articles_repo

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("")
def categories(db: Session = Depends(get_db)) -> list[dict]:
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    result = []
    for cat in ALL_CATEGORIES:
        latest = analyses_repo.latest_analysis(db, cat, "daily")
        result.append(
            {
                "category": cat,
                "article_count": articles_repo.count_new_since(db, cat, since),
                "latest_daily_id": latest.id if latest else None,
                "latest_daily_title": latest.title if latest else None,
            }
        )
    return result


@router.get("/{category}/analyses")
def category_analyses(category: str, kind: str | None = None,
                      db: Session = Depends(get_db)) -> dict:
    from app.api.routes_analyses import _summary

    items = analyses_repo.list_analyses(db, category=category, kind=kind)
    return {"items": [_summary(a) for a in items]}
```

```python
# backend/app/api/routes_articles.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.entities import Article
from app.repositories import articles as repo

router = APIRouter(prefix="/api", tags=["articles"])


def _out(article: Article) -> dict:
    return {
        "id": article.id,
        "category": article.category,
        "title": article.title,
        "url": article.url,
        "summary": article.summary,
        "source_name": article.source.name if article.source else None,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "fetched_at": article.fetched_at.isoformat(),
        "lang": article.lang,
    }


@router.get("/categories/{category}/articles")
def list_articles(category: str, limit: int = Query(default=30, le=100),
                  offset: int = Query(default=0, ge=0),
                  db: Session = Depends(get_db)) -> dict:
    items = repo.list_articles(db, category=category, limit=limit, offset=offset)
    return {"items": [_out(a) for a in items]}


@router.get("/articles/{article_id}")
def get_article(article_id: int, db: Session = Depends(get_db)) -> dict:
    article = repo.get_article(db, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="文章不存在")
    return {**_out(article), "content_text": article.content_text}
```

```python
# backend/app/api/routes_analyses.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.entities import Analysis
from app.repositories import analyses as repo

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


def _summary(analysis: Analysis) -> dict:
    return {
        "id": analysis.id,
        "kind": analysis.kind,
        "category": analysis.category,
        "title": analysis.title,
        "status": analysis.status,
        "created_at": analysis.created_at.isoformat(),
        "model": analysis.model,
    }


@router.get("")
def list_analyses(category: str | None = None, kind: str | None = None,
                  limit: int = Query(default=50, le=200),
                  db: Session = Depends(get_db)) -> dict:
    return {"items": [_summary(a) for a in repo.list_analyses(db, category=category, kind=kind, limit=limit)]}


@router.get("/{analysis_id}")
def get_analysis(analysis_id: int, db: Session = Depends(get_db)) -> dict:
    analysis = repo.get_analysis(db, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="分析不存在")
    citations = []
    for link in analysis.article_links:
        art = link.article
        if art:
            citations.append(
                {
                    "id": art.id,
                    "title": art.title,
                    "url": art.url,
                    "source_name": art.source.name if art.source else None,
                }
            )
    return {
        **_summary(analysis),
        "content_md": analysis.content_md,
        "period_start": analysis.period_start.isoformat(),
        "period_end": analysis.period_end.isoformat(),
        "error": analysis.error,
        "citations": citations,
    }
```

```python
# backend/app/api/routes_logs.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories import logs as repo

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
def list_logs(limit: int = Query(default=50, le=200),
              db: Session = Depends(get_db)) -> dict:
    items = []
    for log in repo.list_logs(db, limit=limit):
        task = None
        if log.task_id:
            from app.repositories import tasks as tasks_repo

            task = tasks_repo.get_task(db, log.task_id)
        items.append(
            {
                "id": log.id,
                "task_id": log.task_id,
                "task_name": task.name if task else None,
                "started_at": log.started_at.isoformat(),
                "finished_at": log.finished_at.isoformat() if log.finished_at else None,
                "status": log.status,
                "fetched_count": log.fetched_count,
                "new_count": log.new_count,
                "error": log.error,
            }
        )
    return {"items": items}
```

- [ ] **Step 4: 运行通过**

Run: `cd backend && uv run pytest tests/test_api_content.py -q`
Expected: 2 passed（需 Task 15 app 装配完成）。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat(backend): 内容与仪表盘 API"
```

---

### Task 14: 任务 API 与手动执行

**Files:**
- Create: `backend/app/api/routes_tasks.py`
- Test: `backend/tests/test_api_tasks.py`

- [ ] **Step 1: 写失败测试**

```python
def test_task_crud_and_manual_run(client, monkeypatch):
    from app.api import routes_tasks

    listed = client.get("/api/tasks").json()["items"]
    assert len(listed) == 2  # 种子默认任务

    body = {"name": "军事采集", "kind": "collect", "category": "military", "cron": "0 */6 * * *"}
    created = client.post("/api/tasks", json=body)
    assert created.status_code == 201
    task_id = created.json()["id"]

    patched = client.patch(f"/api/tasks/{task_id}", json={"enabled": False})
    assert patched.status_code == 200 and patched.json()["enabled"] is False

    monkeypatch.setattr(
        routes_tasks, "run_task_flow",
        lambda db, task, **kwargs: {"task_id": task.id, "status": "success",
                                    "fetched": 5, "new": 4, "errors": []},
    )
    run = client.post(f"/api/tasks/{task_id}/run")
    assert run.status_code == 200
    assert run.json()["status"] == "success" and run.json()["new"] == 4

    assert client.delete(f"/api/tasks/{task_id}").status_code == 204
    assert client.get(f"/api/tasks/{task_id}").status_code == 404


def test_manual_run_missing_task_404(client):
    assert client.post("/api/tasks/99999/run").status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_api_tasks.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现 routes_tasks.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.models.entities import Task
from app.repositories import tasks as repo
from app.services.flow import run_task_flow

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(pattern="^(collect|analyze)$")
    category: str | None = None
    cron: str = Field(min_length=5, max_length=100)
    enabled: bool = True


class TaskPatch(BaseModel):
    name: str | None = None
    kind: str | None = Field(default=None, pattern="^(collect|analyze)$")
    category: str | None = None
    cron: str | None = None
    enabled: bool | None = None


def _out(task: Task) -> dict:
    return {
        "id": task.id,
        "name": task.name,
        "kind": task.kind,
        "category": task.category,
        "cron": task.cron,
        "enabled": task.enabled,
        "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
        "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
    }


def _require(db: Session, task_id: int) -> Task:
    task = repo.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("")
def list_tasks(db: Session = Depends(get_db)) -> dict:
    return {"items": [_out(t) for t in repo.list_tasks(db)]}


@router.get("/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    return _out(_require(db, task_id))


@router.post("", status_code=201)
def create_task(payload: TaskIn, db: Session = Depends(get_db)) -> dict:
    task = repo.create_task(
        db, name=payload.name, kind=payload.kind,
        category=payload.category, cron=payload.cron, enabled=payload.enabled,
    )
    return _out(task)


@router.patch("/{task_id}")
def patch_task(task_id: int, payload: TaskPatch, db: Session = Depends(get_db)) -> dict:
    task = repo.update_task(
        db, _require(db, task_id), name=payload.name, kind=payload.kind,
        category=payload.category, cron=payload.cron, enabled=payload.enabled,
    )
    return _out(task)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)) -> None:
    repo.delete_task(db, _require(db, task_id))


@router.post("/{task_id}/run")
def run_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = _require(db, task_id)
    settings = get_settings()
    return run_task_flow(db, task, settings=settings)
```

- [ ] **Step 4: 运行通过**

Run: `cd backend && uv run pytest tests/test_api_tasks.py -q`
Expected: 2 passed。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat(backend): 任务 API 与手动执行"
```

---

### Task 15: 应用装配与全量验收

**Files:**
- Create: `backend/app/main.py`
- Modify: `backend/app/__init__.py`
- Test: 全量 `cd backend && uv run pytest -q`

- [ ] **Step 1: 实现 main.py**

```python
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.database import Base, make_engine, make_session_factory
from app.services.scheduler import SchedulerManager
from app.services.seed import seed_defaults
from app.api import (  # noqa: F401
    routes_analyses,
    routes_articles,
    routes_categories,
    routes_dashboard,
    routes_health,
    routes_logs,
    routes_sources,
    routes_tasks,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.db_path)
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    scheduler = SchedulerManager(session_factory, settings) if settings.scheduler_enabled else None

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        with session_factory() as db:
            seed_defaults(db, settings)
        if scheduler:
            scheduler.start()
        yield
        if scheduler:
            scheduler.shutdown()
        engine.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    app.include_router(routes_health.router)
    app.include_router(routes_dashboard.router)
    app.include_router(routes_categories.router)
    app.include_router(routes_articles.router)
    app.include_router(routes_analyses.router)
    app.include_router(routes_sources.router)
    app.include_router(routes_tasks.router)
    app.include_router(routes_logs.router)
    return app


app = create_app()
```

注意：模块级 `app = create_app()` 使 `uvicorn app.main:app` 可启动；测试通过 `create_app()` 工厂创建隔离实例。

- [ ] **Step 2: 全量运行测试**

Run: `cd backend && uv run pytest -q`
Expected: **32 passed**（config 2、database 2、models 2、repositories 4、urlutil 3、collector 2、llm 3、analyzer 3、flow 3、scheduler 1、api_sources 3、api_content 2、api_tasks 2；若计数有出入以实际为准，但要求 0 failed）。

- [ ] **Step 3: 真实冒烟（可选，有网络与 Key 时）**

```bash
cp .env.example .env   # 填入 DEEPSEEK_API_KEY
uv run uvicorn app.main:app --port 8000
curl -s http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8000/api/dashboard/summary
```

Expected: health 返回 `{"status":"ok"}`；summary 返回今日统计与源健康。

- [ ] **Step 4: 提交**

```bash
git add backend
git commit -m "feat(backend): 应用装配与路由注册"
```

- [ ] **Step 5: 交付说明（写入 README，供前端计划使用）**

创建 `README.md` 并写入后端启动方式与 API 概览（前端计划会在 B 中补充启动脚本）：

```markdown
# Aurora

全球信息收集与分析系统。仓库结构：

- `backend/`：FastAPI + SQLite + APScheduler（本计划）
- `frontend/`：React + Vite + TS + Ant Design（计划 B）

## 后端启动

```bash
cd backend
cp .env.example .env   # 填入 DEEPSEEK_API_KEY
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

测试：`cd backend && uv run pytest -q`

## 主要 API

- `GET /api/dashboard/summary` 仪表盘统计
- `GET /api/categories`、`GET /api/categories/{cat}/articles`、`GET /api/categories/{cat}/analyses`
- `GET /api/analyses/{id}`、`GET /api/articles/{id}`
- `GET|POST /api/sources`、`PATCH|DELETE /api/sources/{id}`、`POST /api/sources/{id}/test`
- `GET|POST /api/tasks`、`PATCH|DELETE /api/tasks/{id}`、`POST /api/tasks/{id}/run`
- `GET /api/logs`
```

- [ ] **Step 6: 提交 README**

```bash
git add README.md
git commit -m "docs: 后端启动与 API 说明"
```

---

## 计划范围说明

- 本计划覆盖设计文档的后端全部内容（M1、M2、M3 与 M5 的后端部分）。前端五个页面与启动脚本归入**计划 B**，待 A 验收后编写。
- `kv_settings` 表已按规范建模，但第一版运行时配置统一走 `.env`（避免双配置源产生歧义）；后续如需“设置页动态改模型/时段”，再在计划 B 或后续迭代中补充对应 API。
- 种子源 URL 均为官方/机构公开 feed；网络可达性受地域影响，验收时请用 `POST /api/sources/{id}/test` 逐个验证，失效源可在界面替换。
