from fastapi import APIRouter, Depends, HTTPException
from httpx import Client
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.entities import Source
from app.repositories import sources as repo
from app.services.collector import USER_AGENT, fetch_source

router = APIRouter(prefix="/api/sources", tags=["sources"])


class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=5, max_length=2000)
    feed_type: str = Field(default="rss", pattern="^(rss|page)$")
    lang: str = Field(default="en", max_length=10)
    enabled: bool = True
    categories: list[str] = Field(min_length=1)


class SourcePatch(BaseModel):
    name: str | None = None
    url: str | None = None
    feed_type: str | None = Field(default=None, pattern="^(rss|page)$")
    lang: str | None = None
    enabled: bool | None = None
    categories: list[str] | None = None


def _out(source: Source) -> dict:
    return {
        "id": source.id,
        "name": source.name,
        "url": source.url,
        "feed_type": source.feed_type,
        "lang": source.lang,
        "enabled": source.enabled,
        "categories": [sc.category for sc in source.source_categories],
        "last_ok_at": source.last_ok_at.isoformat() if source.last_ok_at else None,
        "last_error": source.last_error,
        "error_count": source.error_count,
    }


def _require_source(db: Session, source_id: int) -> Source:
    source = repo.get_source(db, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="采集源不存在")
    return source


@router.get("")
def list_sources(db: Session = Depends(get_db)) -> dict:
    return {"items": [_out(s) for s in repo.list_sources(db)]}


@router.get("/{source_id}")
def get_source(source_id: int, db: Session = Depends(get_db)) -> dict:
    return _out(_require_source(db, source_id))


@router.post("", status_code=201)
def create_source(payload: SourceIn, db: Session = Depends(get_db)) -> dict:
    try:
        source = repo.create_source(
            db, name=payload.name, url=payload.url, feed_type=payload.feed_type,
            lang=payload.lang, categories=payload.categories, enabled=payload.enabled,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该 URL 已存在") from None
    return _out(source)


@router.patch("/{source_id}")
def patch_source(source_id: int, payload: SourcePatch,
                 db: Session = Depends(get_db)) -> dict:
    source = _require_source(db, source_id)
    try:
        source = repo.update_source(
            db, source, name=payload.name, url=payload.url, feed_type=payload.feed_type,
            lang=payload.lang, enabled=payload.enabled, categories=payload.categories,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该 URL 已存在") from None
    return _out(source)


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)) -> None:
    repo.delete_source(db, _require_source(db, source_id))


@router.post("/{source_id}/test")
def test_source(source_id: int, db: Session = Depends(get_db)) -> dict:
    """真实抓取一次，不入库，只返回前 3 条预览。"""
    source = _require_source(db, source_id)
    try:
        from app.core.config import get_settings

        settings = get_settings()
        with Client(headers={"User-Agent": USER_AGENT}, timeout=settings.request_timeout_s) as http:
            items, error = fetch_source(source, settings, http)
        return {
            "ok": error is None,
            "error": error,
            "preview": [
                {"title": it["title"], "url": it["url"], "published_at": it.get("published_at")}
                for it in items[:3]
            ],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "preview": []}
