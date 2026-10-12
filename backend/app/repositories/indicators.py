from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import MacroIndicator, utcnow


def get_indicator(db: Session, indicator_id: int) -> MacroIndicator | None:
    return db.get(MacroIndicator, indicator_id)


def upsert_indicator(db: Session, *, indicator: str, region: str, period: str,
                     value: float, unit: str = "", previous: float | None = None,
                     forecast: float | None = None,
                     released_at: datetime | None = None, merge_key: str,
                     verification_status: str = "confirmed",
                     confidence: float = 0.8,
                     article_id: int | None = None) -> tuple[MacroIndicator, bool]:
    row = db.query(MacroIndicator).filter(MacroIndicator.merge_key == merge_key).first()
    if row is None:
        row = MacroIndicator(merge_key=merge_key)
        db.add(row)
        created = True
    else:
        created = False
    row.indicator = indicator
    row.region = region
    row.period = period
    row.value = value
    row.unit = unit
    if previous is not None:
        row.previous = previous
    if forecast is not None:
        row.forecast = forecast
    if released_at:
        row.released_at = released_at
    row.verification_status = verification_status
    row.confidence = confidence
    if article_id:
        row.article_id = article_id
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row, created


def list_indicators(db: Session, indicator: str | None = None,
                    region: str | None = None, limit: int = 100) -> list[MacroIndicator]:
    query = db.query(MacroIndicator)
    if indicator:
        query = query.filter(MacroIndicator.indicator == indicator)
    if region:
        query = query.filter(MacroIndicator.region == region)
    return query.order_by(MacroIndicator.released_at.desc().nullslast(),
                          MacroIndicator.updated_at.desc()).limit(limit).all()


def update_indicator(db: Session, row: MacroIndicator, *,
                     value: float | None = None, previous: float | None = None,
                     forecast: float | None = None,
                     verification_status: str | None = None) -> MacroIndicator:
    if value is not None:
        row.value = value
    if previous is not None:
        row.previous = previous
    if forecast is not None:
        row.forecast = forecast
    if verification_status is not None:
        row.verification_status = verification_status
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row
