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
