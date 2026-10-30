from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.entities import Article, TimelineEvent, utcnow


def get_event(db: Session, event_id: int) -> TimelineEvent | None:
    return db.get(TimelineEvent, event_id)


def upsert_event(db: Session, *, category: str, subtype: str, actor: str = "",
                 region: str = "", occurred_at: datetime | None = None,
                 summary: str = "", importance: str = "medium",
                 verification_status: str = "draft", confidence: float = 0.5,
                 article_id: int | None = None, group_key: str | None = None,
                 merge_key: str) -> tuple[TimelineEvent, bool]:
    row = db.query(TimelineEvent).filter(TimelineEvent.merge_key == merge_key).first()
    if row is None:
        row = TimelineEvent(category=category, subtype=subtype, merge_key=merge_key)
        db.add(row)
        created = True
    else:
        created = False
    row.category = category
    row.subtype = subtype
    row.actor = actor
    row.region = region
    if occurred_at:
        row.occurred_at = max(row.occurred_at, occurred_at) if row.occurred_at else occurred_at
    if summary:
        row.summary = summary
    row.importance = importance
    row.confidence = confidence
    if row.verification_status != "confirmed" and verification_status == "confirmed":
        row.verification_status = "confirmed"
    if group_key:
        row.group_key = group_key
    if article_id:
        row.article_id = article_id
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row, created


def list_events(db: Session, category: str | None = None,
                subtype: str | None = None, verification: str | None = None,
                limit: int = 100, since: datetime | None = None) -> list[TimelineEvent]:
    query = db.query(TimelineEvent)
    if category:
        query = query.filter(TimelineEvent.category == category)
    if subtype:
        query = query.filter(TimelineEvent.subtype == subtype)
    if verification:
        query = query.filter(TimelineEvent.verification_status == verification)
    if since:
        query = query.filter(
            or_(TimelineEvent.occurred_at.is_(None), TimelineEvent.occurred_at >= since)
        )
    return query.order_by(TimelineEvent.occurred_at.desc().nullslast(),
                          TimelineEvent.updated_at.desc()).limit(limit).all()


def update_event(db: Session, row: TimelineEvent, *, summary: str | None = None,
                 actor: str | None = None, region: str | None = None,
                 importance: str | None = None,
                 verification_status: str | None = None) -> TimelineEvent:
    if summary is not None:
        row.summary = summary
    if actor is not None:
        row.actor = actor
    if region is not None:
        row.region = region
    if importance is not None:
        row.importance = importance
    if verification_status is not None:
        row.verification_status = verification_status
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row


def backfill_missing_times(db: Session) -> int:
    """用关联文章发布时间补齐缺失的事件时间；无文章时回落到入库时间。"""
    rows = db.query(TimelineEvent).filter(TimelineEvent.occurred_at.is_(None)).all()
    for row in rows:
        article = db.get(Article, row.article_id) if row.article_id else None
        row.occurred_at = (
            (article.published_at or article.fetched_at) if article else row.created_at
        )
    if rows:
        db.commit()
    return len(rows)
