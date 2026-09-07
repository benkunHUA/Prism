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
