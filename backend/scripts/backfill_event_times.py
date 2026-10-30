#!/usr/bin/env python
"""回填缺失的事件时间，优先使用关联文章的发布时间。

用法（在 backend 目录下执行）：

    uv run python scripts/backfill_event_times.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.database import make_engine, make_session_factory  # noqa: E402
from app.core.schema import ensure_schema  # noqa: E402
from app.repositories.timeline import backfill_missing_times  # noqa: E402


def main() -> int:
    settings = get_settings()
    engine = make_engine(settings.db_path)
    ensure_schema(engine)
    session = make_session_factory(engine)()
    try:
        count = backfill_missing_times(session)
        print(f"完成：回填 {count} 条事件时间")
        return 0
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
