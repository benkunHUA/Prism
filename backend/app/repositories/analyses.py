from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import Analysis, AnalysisArticle


def list_analyses(db: Session, category: str | None = None,
                  kind: str | None = None, limit: int = 50) -> list[Analysis]:
    query = db.query(Analysis)
    if category:
        query = query.filter(Analysis.category == category)
    if kind:
        query = query.filter(Analysis.kind == kind)
    return query.order_by(Analysis.created_at.desc()).limit(limit).all()


def get_analysis(db: Session, analysis_id: int) -> Analysis | None:
    return db.get(Analysis, analysis_id)


def create_analysis(db: Session, *, kind: str, category: str, title: str,
                    content_md: str, period_start: datetime | None,
                    period_end: datetime | None, model: str,
                    status: str = "success", error: str | None = None) -> Analysis:
    analysis = Analysis(
        kind=kind, category=category, title=title, content_md=content_md,
        period_start=period_start, period_end=period_end, model=model,
        status=status, error=error,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def link_articles(db: Session, analysis: Analysis, article_ids: list[int]) -> None:
    for aid in dict.fromkeys(article_ids):
        analysis.article_links.append(AnalysisArticle(article_id=aid))
    db.commit()


def latest_analysis(db: Session, category: str, kind: str) -> Analysis | None:
    return (
        db.query(Analysis)
        .filter(Analysis.category == category, Analysis.kind == kind)
        .order_by(Analysis.created_at.desc())
        .first()
    )


def count_daily_since(db: Session, since: datetime) -> int:
    return (
        db.query(Analysis)
        .filter(
            Analysis.kind == "daily",
            Analysis.status == "success",
            Analysis.created_at >= since,
        )
        .count()
    )
