from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.entities import Analysis
from app.repositories import analyses as repo

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


def _summary(analysis: Analysis) -> dict:
    return {
        "id": analysis.id,
        "kind": analysis.kind,
        "category": analysis.category,
        "title": analysis.title,
        "status": analysis.status,
        "created_at": analysis.created_at.isoformat(),
        "model": analysis.model,
    }


@router.get("")
def list_analyses(category: str | None = None, kind: str | None = None,
                  limit: int = Query(default=50, le=200),
                  db: Session = Depends(get_db)) -> dict:
    items = repo.list_analyses(db, category=category, kind=kind, limit=limit)
    return {"items": [_summary(a) for a in items]}


@router.get("/{analysis_id}")
def get_analysis(analysis_id: int, db: Session = Depends(get_db)) -> dict:
    analysis = repo.get_analysis(db, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="分析不存在")
    citations = []
    for link in analysis.article_links:
        art = link.article
        if art:
            citations.append(
                {
                    "id": art.id,
                    "title": art.title,
                    "url": art.url,
                    "source_name": art.source.name if art.source else None,
                }
            )
    return {
        **_summary(analysis),
        "content_md": analysis.content_md,
        "period_start": analysis.period_start.isoformat(),
        "period_end": analysis.period_end.isoformat(),
        "error": analysis.error,
        "citations": citations,
    }
