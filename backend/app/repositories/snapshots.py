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


def recent_batch_ids(db: Session, limit: int = 2) -> list[str]:
    """按抓取时间倒序返回最近的批次 id，用于「较上轮」对比。"""

    rows = (
        db.query(MarketSnapshot.batch_id, MarketSnapshot.captured_at)
        .order_by(MarketSnapshot.captured_at.desc())
        .limit(200)
        .all()
    )
    ids: list[str] = []
    for batch_id, _ in rows:
        if batch_id and batch_id not in ids:
            ids.append(batch_id)
        if len(ids) >= limit:
            break
    return ids
