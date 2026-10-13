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
