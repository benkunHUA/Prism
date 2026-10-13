from sqlalchemy import inspect, text

from app.core.database import make_engine
from app.core.schema import ensure_schema

# 旧版本 sources 表：没有地理功能引入的 region 列。
LEGACY_SOURCES_DDL = """
CREATE TABLE sources (
    id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    url VARCHAR(2000) NOT NULL UNIQUE,
    feed_type VARCHAR(10) NOT NULL,
    lang VARCHAR(10) NOT NULL,
    enabled BOOLEAN NOT NULL,
    last_ok_at DATETIME,
    last_error TEXT,
    error_count INTEGER NOT NULL,
    created_at DATETIME NOT NULL
)
"""


def _legacy_engine(tmp_path):
    engine = make_engine(str(tmp_path / "legacy.db"))
    with engine.begin() as conn:
        conn.execute(text(LEGACY_SOURCES_DDL))
    return engine


def test_ensure_schema_backfills_missing_column_and_tables(tmp_path):
    engine = _legacy_engine(tmp_path)
    added = ensure_schema(engine)
    assert "sources.region" in added
    assert "region" in {c["name"] for c in inspect(engine).get_columns("sources")}
    assert "article_regions" in inspect(engine).get_table_names()
    engine.dispose()


def test_ensure_schema_is_idempotent(tmp_path):
    engine = _legacy_engine(tmp_path)
    ensure_schema(engine)
    assert ensure_schema(engine) == []
    engine.dispose()


def test_ensure_schema_creates_tables_on_fresh_db(tmp_path):
    engine = make_engine(str(tmp_path / "fresh.db"))
    assert ensure_schema(engine) == []
    assert "articles" in inspect(engine).get_table_names()
    engine.dispose()


# 旧版本 articles 表：没有翻译功能引入的 title_zh / summary_zh。
LEGACY_ARTICLES_DDL = """
CREATE TABLE articles (
    id INTEGER NOT NULL PRIMARY KEY,
    source_id INTEGER,
    category VARCHAR(20) NOT NULL,
    url VARCHAR(2000) NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    summary TEXT NOT NULL,
    content_text TEXT NOT NULL,
    published_at DATETIME,
    fetched_at DATETIME NOT NULL,
    dedupe_hash VARCHAR(64) NOT NULL,
    lang VARCHAR(10) NOT NULL
)
"""


def test_ensure_schema_backfills_translation_columns(tmp_path):
    engine = make_engine(str(tmp_path / "legacy_articles.db"))
    with engine.begin() as conn:
        conn.execute(text(LEGACY_ARTICLES_DDL))

    added = ensure_schema(engine)

    assert "articles.title_zh" in added
    assert "articles.summary_zh" in added
    columns = {c["name"] for c in inspect(engine).get_columns("articles")}
    assert {"title_zh", "summary_zh"} <= columns
    engine.dispose()
