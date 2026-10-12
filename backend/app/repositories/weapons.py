from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import MilitaryWeapon, utcnow


def get_weapon(db: Session, weapon_id: int) -> MilitaryWeapon | None:
    return db.get(MilitaryWeapon, weapon_id)


def upsert_weapon(db: Session, *, name: str, original_name: str = "", origin: str = "",
                  weapon_type: str = "", params_text: str = "",
                  lifecycle_status: str = "研发", merge_key: str,
                  verification_status: str = "draft", confidence: float = 0.5,
                  article_id: int | None = None,
                  first_seen_at: datetime | None = None) -> tuple[MilitaryWeapon, bool]:
    row = db.query(MilitaryWeapon).filter(MilitaryWeapon.merge_key == merge_key).first()
    now = utcnow()
    if row is None:
        row = MilitaryWeapon(merge_key=merge_key, first_seen_at=first_seen_at or now)
        db.add(row)
        created = True
    else:
        created = False
    row.name = name
    row.original_name = original_name
    row.origin = origin
    row.weapon_type = weapon_type
    if params_text:
        row.params_text = params_text
    if lifecycle_status:
        row.lifecycle_status = lifecycle_status
    row.confidence = confidence
    if row.verification_status != "confirmed" and verification_status == "confirmed":
        row.verification_status = "confirmed"
    if article_id:
        row.article_id = article_id
    row.last_seen_at = now
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return row, created


def list_weapons(db: Session, lifecycle: str | None = None,
                 verification: str | None = None,
                 limit: int = 100) -> list[MilitaryWeapon]:
    query = db.query(MilitaryWeapon)
    if lifecycle:
        query = query.filter(MilitaryWeapon.lifecycle_status == lifecycle)
    if verification:
        query = query.filter(MilitaryWeapon.verification_status == verification)
    return query.order_by(MilitaryWeapon.updated_at.desc()).limit(limit).all()


def update_weapon(db: Session, row: MilitaryWeapon, *, name: str | None = None,
                  origin: str | None = None, weapon_type: str | None = None,
                  params_text: str | None = None,
                  lifecycle_status: str | None = None,
                  verification_status: str | None = None) -> MilitaryWeapon:
    for field, value in (("name", name), ("origin", origin), ("weapon_type", weapon_type),
                         ("params_text", params_text),
                         ("lifecycle_status", lifecycle_status),
                         ("verification_status", verification_status)):
        if value is not None:
            setattr(row, field, value)
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row
