from sqlalchemy.orm import Session

from app.models.entities import MarketSnapshot


def insert_snapshots(db: Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    db.add_all([MarketSnapshot(**row) for row in rows])
    db.commit()
    return len(rows)


def latest_batch_id(db: Session) -> str | None:
    row = db.query(MarketSnapshot).order_by(MarketSnapshot.captured_at.desc()).first()
    return row.batch_id if row else None


def list_snapshots(db: Session, batch_id: str | None = None,
                   asset_class: str | None = None,
                   limit: int = 200) -> list[MarketSnapshot]:
    query = db.query(MarketSnapshot)
    if batch_id:
        query = query.filter(MarketSnapshot.batch_id == batch_id)
    if asset_class:
        query = query.filter(MarketSnapshot.asset_class == asset_class)
    return (
        query.order_by(MarketSnapshot.captured_at.desc(), MarketSnapshot.asset_code)
        .limit(limit)
        .all()
    )
