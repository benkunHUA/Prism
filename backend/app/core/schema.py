"""启动时把库结构补齐到当前模型定义。

项目没有引入 Alembic：历史库由旧版本建立，而 create_all 只会新建缺失的表、
不会给已有表补列（例如地理功能给 sources 增加的 region），
所以这里在 create_all 之后用 ALTER TABLE 补齐缺失列，可重复执行。
"""

from __future__ import annotations

from sqlalchemy import DateTime, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import Column
from sqlalchemy.sql.sqltypes import Boolean, Integer, Numeric

from app.core.database import Base


def ensure_schema(engine: Engine) -> list[str]:
    """建缺失的表并补缺失的列，返回本次补过的 "表.列"。"""
    Base.metadata.create_all(engine)
    added: list[str] = []
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        present = {column["name"] for column in inspector.get_columns(table.name)}
        missing = [column for column in table.columns if column.name not in present]
        if not missing:
            continue
        with engine.begin() as conn:
            for column in missing:
                conn.execute(text(_add_column_ddl(table, column, engine)))
                added.append(f"{table.name}.{column.name}")
    return added


def _add_column_ddl(table, column: Column, engine: Engine) -> str:
    column_type = column.type.compile(dialect=engine.dialect)
    return f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}{_default_clause(column)}'


def _default_clause(column: Column) -> str:
    """补列要给已有行填充值：优先用模型的标量默认值，否则按类型兜底。"""
    if column.default is not None and not column.default.is_callable:
        return f" DEFAULT {_literal(column.default.arg)}"
    if column.nullable:
        return ""
    return f" DEFAULT {_type_fallback(column)}"


def _type_fallback(column: Column) -> str:
    if isinstance(column.type, (Boolean, Integer, Numeric)):
        return "0"
    if isinstance(column.type, DateTime):
        return "CURRENT_TIMESTAMP"
    return "''"


def _literal(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"
