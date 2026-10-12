# backend/app/repositories/article_regions.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import Article, ArticleRegion


def write_regions(db: Session, *, article_id: int, codes: list[str],
                  source: str = "llm") -> int:
    """写入文章地区标签：按 code 去重、跳过已存在的，返回新增条数。"""
    unique = [code for code in dict.fromkeys(codes) if code]
    if not unique:
        return 0
    existing = {
        row[0]
        for row in db.query(ArticleRegion.region_code)
        .filter(ArticleRegion.article_id == article_id,
                ArticleRegion.region_code.in_(unique))
        .all()
    }
    created = 0
    for code in unique:
        if code in existing:
            continue
        db.add(ArticleRegion(article_id=article_id, region_code=code, source=source))
        created += 1
    db.commit()
    return created


def codes_for_article(db: Session, article_id: int) -> set[str]:
    return {
        row[0]
        for row in db.query(ArticleRegion.region_code)
        .filter(ArticleRegion.article_id == article_id)
        .all()
    }


def article_ids_with_regions(db: Session, article_ids: list[int]) -> set[int]:
    if not article_ids:
        return set()
    return {
        row[0]
        for row in db.query(ArticleRegion.article_id)
        .filter(ArticleRegion.article_id.in_(article_ids))
        .distinct()
        .all()
    }


def count_by_region(db: Session, since: datetime) -> list[tuple[str, str, int]]:
    """返回 (region_code, category, 文章数)，只统计窗口内的文章。"""
    rows = (
        db.query(ArticleRegion.region_code, Article.category,
                 func.count(ArticleRegion.id))
        .join(Article, Article.id == ArticleRegion.article_id)
        .filter(Article.fetched_at >= since)
        .group_by(ArticleRegion.region_code, Article.category)
        .all()
    )
    return [(row[0], row[1], row[2]) for row in rows]


def untagged_count(db: Session, since: datetime) -> int:
    tagged = db.query(ArticleRegion.article_id).distinct()
    return (
        db.query(func.count(Article.id))
        .filter(Article.fetched_at >= since, ~Article.id.in_(tagged))
        .scalar()
        or 0
    )


def list_articles_by_region(db: Session, *, code: str, since: datetime,
                            category: str | None = None,
                            limit: int = 30, offset: int = 0) -> list[Article]:
    query = (
        db.query(Article)
        .join(ArticleRegion, ArticleRegion.article_id == Article.id)
        .filter(ArticleRegion.region_code == code, Article.fetched_at >= since)
    )
    if category:
        query = query.filter(Article.category == category)
    return query.order_by(Article.fetched_at.desc()).offset(offset).limit(limit).all()
