#!/usr/bin/env python
"""回填历史文章的标题与摘要译文（可反复执行，只补未完成的）。

用法（在 backend 目录下执行）：

    uv run python scripts/backfill_translations.py
    uv run python scripts/backfill_translations.py --limit 20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.database import make_engine, make_session_factory  # noqa: E402
from app.models.entities import Article  # noqa: E402
from app.services.llm import get_provider  # noqa: E402
from app.services.translation.translator import translate_articles  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="回填文章译文")
    parser.add_argument("--limit", type=int, default=0, help="最多处理多少篇，0 表示不限")
    args = parser.parse_args()

    settings = get_settings()
    engine = make_engine(settings.db_path)
    provider = get_provider(settings)
    session = make_session_factory(engine)()
    try:
        query = (session.query(Article)
                 .filter(Article.title_zh.is_(None))
                 .order_by(Article.id))
        rows = query.limit(args.limit).all() if args.limit else query.all()
        total = len(rows)
        print(f"待翻译 {total} 篇（批大小 {settings.translate_batch_size}）")
        done = failed = 0
        size = max(1, settings.translate_batch_size)
        for start in range(0, total, size):
            batch = rows[start:start + size]
            batch_done, batch_errors = translate_articles(session, batch, provider, settings)
            done += batch_done
            failed += len(batch_errors)
            print(f"  已处理 {start + len(batch)}/{total}｜成功 {done}｜失败 {failed}")
            for message in batch_errors:
                print(f"    - {message}")
        print(f"完成：成功 {done}，失败 {failed}")
        return 0 if failed == 0 else 1
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
