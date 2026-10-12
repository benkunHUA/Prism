from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.serializers import article_out
from app.repositories import articles as repo

router = APIRouter(prefix="/api", tags=["articles"])


@router.get("/categories/{category}/articles")
def list_articles(category: str, limit: int = Query(default=30, le=100),
                  offset: int = Query(default=0, ge=0),
                  db: Session = Depends(get_db)) -> dict:
    items = repo.list_articles(db, category=category, limit=limit, offset=offset)
    return {"items": [article_out(a) for a in items]}


@router.get("/articles/{article_id}")
def get_article(article_id: int, db: Session = Depends(get_db)) -> dict:
    article = repo.get_article(db, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="文章不存在")
    return {**article_out(article), "content_text": article.content_text}
