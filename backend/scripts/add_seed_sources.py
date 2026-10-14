#!/usr/bin/env python
"""给已有数据库补齐内置源（按 URL 去重，可反复执行）。

用法（在 backend 目录下执行）：

    uv run python scripts/add_seed_sources.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.database import make_engine, make_session_factory  # noqa: E402
from app.core.schema import ensure_schema  # noqa: E402
from app.services.seed import add_missing_seed_sources  # noqa: E402


def main() -> int:
    settings = get_settings()
    engine = make_engine(settings.db_path)
    ensure_schema(engine)
    session = make_session_factory(engine)()
    try:
        added = add_missing_seed_sources(session)
        if not added:
            print("没有需要补充的内置源")
            return 0
        for name in added:
            print(f"  已添加 {name}")
        print(f"完成：新增 {len(added)} 个源")
        return 0
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
