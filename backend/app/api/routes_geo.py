from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.serializers import article_out
from app.core.constants import ALL_CATEGORIES
from app.core.geo import REGION_MAP
from app.repositories import article_regions as article_regions_repo
from app.repositories import articles as articles_repo

router = APIRouter(prefix="/api", tags=["geo"])

WINDOW_HOURS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}


def window_start(window: str) -> datetime:
    hours = WINDOW_HOURS.get(window)
    if hours is None:
        raise HTTPException(status_code=422, detail="window 仅支持 24h / 7d / 30d")
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)


@router.get("/dashboard/geo")
def dashboard_geo(window: str = Query(default="24h"),
                  db: Session = Depends(get_db)) -> dict:
    since = window_start(window)
    buckets: dict[str, dict] = {}
    for code, category, count in article_regions_repo.count_by_region(db, since):
        entry = buckets.setdefault(
            code, {"count": 0, "by_category": {c: 0 for c in ALL_CATEGORIES}}
        )
        entry["count"] += count
        entry["by_category"][category] = entry["by_category"].get(category, 0) + count

    regions = []
    for code, entry in buckets.items():
        info = REGION_MAP.get(code)
        if info is None:  # 词表里被删掉的历史标签，跳过而不是报错
            continue
        regions.append({
            "code": code, "name": info["name_zh"],
            "lng": info["lng"], "lat": info["lat"],
            "count": entry["count"], "by_category": entry["by_category"],
        })
    regions.sort(key=lambda item: (-item["count"], item["code"]))
    return {
        "window": window,
        "window_start": since.isoformat(),
        "total": articles_repo.count_all_since(db, since),
        "untagged": article_regions_repo.untagged_count(db, since),
        "regions": regions,
    }


@router.get("/regions/{code}/articles")
def region_articles(code: str, window: str = Query(default="24h"),
                    category: str | None = None,
                    limit: int = Query(default=30, le=100),
                    offset: int = Query(default=0, ge=0),
                    db: Session = Depends(get_db)) -> dict:
    info = REGION_MAP.get(code)
    if info is None:
        raise HTTPException(status_code=404, detail="未知地区")
    since = window_start(window)
    items = article_regions_repo.list_articles_by_region(
        db, code=code, since=since, category=category, limit=limit, offset=offset
    )
    return {"region": code, "name": info["name_zh"], "window": window,
            "items": [article_out(article) for article in items]}
