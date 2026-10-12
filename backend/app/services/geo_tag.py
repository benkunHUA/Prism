from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.geo import normalize_region
from app.models.entities import Article
from app.repositories import article_regions as article_regions_repo


def backfill_source_regions(db: Session, articles: list[Article]) -> int:
    """给还没有任何地区标签的文章补一条来源地区标签，返回补标条数。

    只兜底、不覆盖：已有标签的文章跳过；来源没配 region 的文章保持未标注。
    """
    if not articles:
        return 0
    tagged = article_regions_repo.article_ids_with_regions(db, [a.id for a in articles])
    created = 0
    for article in articles:
        if article.id in tagged:
            continue
        code = normalize_region(article.source.region if article.source else "")
        if not code:
            continue
        created += article_regions_repo.write_regions(
            db, article_id=article.id, codes=[code], source="source"
        )
    return created
