from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.constants import ALL_CATEGORIES
from app.repositories import analyses as analyses_repo
from app.repositories import articles as articles_repo

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("")
def categories(db: Session = Depends(get_db)) -> list[dict]:
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    result = []
    for cat in ALL_CATEGORIES:
        latest = analyses_repo.latest_analysis(db, cat, "daily")
        result.append(
            {
                "category": cat,
                "article_count": articles_repo.count_new_since(db, cat, since),
                "latest_daily_id": latest.id if latest else None,
                "latest_daily_title": latest.title if latest else None,
            }
        )
    return result


@router.get("/{category}/analyses")
def category_analyses(category: str, kind: str | None = None,
                      db: Session = Depends(get_db)) -> dict:
    from app.api.routes_analyses import _summary

    items = analyses_repo.list_analyses(db, category=category, kind=kind)
    return {"items": [_summary(a) for a in items]}
