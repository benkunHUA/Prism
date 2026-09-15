from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories import indicators as indicators_repo
from app.repositories import snapshots as snapshots_repo
from app.repositories import stances as stances_repo
from app.repositories import timeline as timeline_repo
from app.repositories import weapons as weapons_repo

router = APIRouter(prefix="/api", tags=["boards"])


def _event_out(e) -> dict:
    return {
        "id": e.id, "category": e.category, "subtype": e.subtype, "actor": e.actor,
        "region": e.region, "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
        "summary": e.summary, "importance": e.importance,
        "verification_status": e.verification_status, "group_key": e.group_key,
        "article_id": e.article_id, "updated_at": e.updated_at.isoformat(),
    }


def _weapon_out(w) -> dict:
    return {"id": w.id, "name": w.name, "origin": w.origin, "weapon_type": w.weapon_type,
            "params_text": w.params_text, "lifecycle_status": w.lifecycle_status,
            "verification_status": w.verification_status,
            "first_seen_at": w.first_seen_at.isoformat() if w.first_seen_at else None}


def _indicator_out(i) -> dict:
    return {"id": i.id, "indicator": i.indicator, "region": i.region, "period": i.period,
            "value": i.value, "unit": i.unit, "previous": i.previous,
            "forecast": i.forecast,
            "released_at": i.released_at.isoformat() if i.released_at else None}


def _stance_out(s) -> dict:
    return {"id": s.id, "topic": s.topic, "actor": s.actor, "stance_text": s.stance_text,
            "tone": s.tone, "stated_at": s.stated_at.isoformat() if s.stated_at else None,
            "verification_status": s.verification_status}


@router.get("/categories/{category}/timeline")
def category_timeline(category: str, subtype: str | None = None,
                      importance: str | None = None,
                      limit: int = Query(default=100, le=200),
                      db: Session = Depends(get_db)) -> dict:
    items = timeline_repo.list_events(db, category=category, subtype=subtype,
                                      verification="confirmed", limit=limit)
    if importance:
        items = [e for e in items if e.importance == importance]
    return {"items": [_event_out(e) for e in items]}


@router.get("/military/weapons")
def military_weapons(lifecycle: str | None = None,
                     limit: int = Query(default=100, le=200),
                     db: Session = Depends(get_db)) -> dict:
    return {"items": [_weapon_out(w) for w in weapons_repo.list_weapons(
        db, lifecycle=lifecycle, verification="confirmed", limit=limit)]}


@router.get("/economy/indicators")
def economy_indicators(indicator: str | None = None, region: str | None = None,
                       limit: int = Query(default=100, le=200),
                       db: Session = Depends(get_db)) -> dict:
    return {"items": [_indicator_out(i) for i in indicators_repo.list_indicators(
        db, indicator=indicator, region=region, limit=limit)]}


@router.get("/politics/stances")
def politics_stances(topic: str | None = None, actor: str | None = None,
                     limit: int = Query(default=200, le=500),
                     db: Session = Depends(get_db)) -> dict:
    rows = stances_repo.list_stances(db, topic=topic, actor=actor,
                                     verification="confirmed", limit=limit)
    latest: dict[tuple, object] = {}
    for row in rows:
        latest.setdefault((row.topic, row.actor), row)
    return {"items": [_stance_out(s) for s in latest.values()]}


@router.get("/finance/snapshots")
def finance_snapshots(batch_id: str | None = None, asset_class: str | None = None,
                      limit: int = Query(default=200, le=500),
                      db: Session = Depends(get_db)) -> dict:
    items = [
        {"id": s.id, "asset_code": s.asset_code, "asset_name": s.asset_name,
         "asset_class": s.asset_class, "price": s.price, "change_pct": s.change_pct,
         "captured_at": s.captured_at.isoformat(), "batch_id": s.batch_id,
         "source": s.source}
        for s in snapshots_repo.list_snapshots(db, batch_id=batch_id,
                                               asset_class=asset_class, limit=limit)
    ]
    return {"items": items}
