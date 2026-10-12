from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import StanceTopic


def get_stance(db: Session, stance_id: int) -> StanceTopic | None:
    return db.get(StanceTopic, stance_id)


def create_stance(db: Session, *, topic: str, actor: str, stance_text: str,
                  tone: str = "中性", stated_at: datetime | None = None,
                  verification_status: str = "draft", confidence: float = 0.5,
                  article_id: int | None = None) -> StanceTopic:
    row = StanceTopic(topic=topic, actor=actor, stance_text=stance_text, tone=tone,
                      stated_at=stated_at, verification_status=verification_status,
                      confidence=confidence, article_id=article_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_stances(db: Session, topic: str | None = None, actor: str | None = None,
                 verification: str | None = None,
                 limit: int = 200) -> list[StanceTopic]:
    query = db.query(StanceTopic)
    if topic:
        query = query.filter(StanceTopic.topic == topic)
    if actor:
        query = query.filter(StanceTopic.actor == actor)
    if verification:
        query = query.filter(StanceTopic.verification_status == verification)
    return query.order_by(StanceTopic.stated_at.desc().nullslast(),
                          StanceTopic.created_at.desc()).limit(limit).all()


def update_stance(db: Session, row: StanceTopic, *, stance_text: str | None = None,
                  tone: str | None = None,
                  verification_status: str | None = None) -> StanceTopic:
    if stance_text is not None:
        row.stance_text = stance_text
    if tone is not None:
        row.tone = tone
    if verification_status is not None:
        row.verification_status = verification_status
    db.commit()
    db.refresh(row)
    return row
