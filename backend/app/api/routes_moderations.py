from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories import indicators as indicators_repo
from app.repositories import stances as stances_repo
from app.repositories import timeline as timeline_repo
from app.repositories import weapons as weapons_repo

router = APIRouter(prefix="/api/moderations", tags=["moderations"])


class ModerationPatch(BaseModel):
    action: str  # confirm | edit | reject
    value: float | None = None
    summary: str | None = None
    importance: str | None = None
    params_text: str | None = None
    lifecycle_status: str | None = None
    stance_text: str | None = None
    tone: str | None = None


def _queue_rows(db: Session, category: str | None, limit: int) -> list[dict]:
    rows = []
    for event in timeline_repo.list_events(db, category=category,
                                           verification="draft", limit=limit):
        rows.append({"type": "timeline", "id": event.id,
                     "category": event.category, "subtype": event.subtype,
                     "summary": event.summary, "importance": event.importance,
                     "verification_status": event.verification_status})
    for weapon in weapons_repo.list_weapons(db, verification="draft", limit=limit):
        rows.append({"type": "weapon", "id": weapon.id, "name": weapon.name,
                     "origin": weapon.origin, "params_text": weapon.params_text,
                     "lifecycle_status": weapon.lifecycle_status,
                     "verification_status": weapon.verification_status})
    for stance in stances_repo.list_stances(db, verification="draft", limit=limit):
        rows.append({"type": "stance", "id": stance.id, "topic": stance.topic,
                     "actor": stance.actor, "stance_text": stance.stance_text,
                     "tone": stance.tone, "verification_status": stance.verification_status})
    for indicator in indicators_repo.list_indicators(db, limit=limit):
        if indicator.verification_status == "draft":
            rows.append({"type": "indicator", "id": indicator.id,
                         "indicator": indicator.indicator, "region": indicator.region,
                         "period": indicator.period, "value": indicator.value,
                         "verification_status": indicator.verification_status})
    return rows


@router.get("")
def list_moderations(category: str | None = None,
                     limit: int = Query(default=100, le=500),
                     db: Session = Depends(get_db)) -> dict:
    return {"items": _queue_rows(db, category, limit)}


def _apply(db: Session, type_: str, item_id: int, payload: ModerationPatch):
    if type_ == "timeline":
        row = timeline_repo.get_event(db, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail="不存在")
        if payload.action == "confirm":
            return timeline_repo.update_event(db, row, verification_status="confirmed")
        if payload.action == "reject":
            return timeline_repo.update_event(db, row, verification_status="rejected")
        return timeline_repo.update_event(db, row, summary=payload.summary,
                                          importance=payload.importance)
    if type_ == "weapon":
        row = weapons_repo.get_weapon(db, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail="不存在")
        if payload.action == "confirm":
            return weapons_repo.update_weapon(db, row, verification_status="confirmed")
        if payload.action == "reject":
            return weapons_repo.update_weapon(db, row, verification_status="rejected")
        return weapons_repo.update_weapon(db, row, params_text=payload.params_text,
                                          lifecycle_status=payload.lifecycle_status)
    if type_ == "stance":
        row = stances_repo.get_stance(db, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail="不存在")
        if payload.action == "confirm":
            return stances_repo.update_stance(db, row, verification_status="confirmed")
        if payload.action == "reject":
            return stances_repo.update_stance(db, row, verification_status="rejected")
        return stances_repo.update_stance(db, row, stance_text=payload.stance_text,
                                          tone=payload.tone)
    if type_ == "indicator":
        row = indicators_repo.get_indicator(db, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail="不存在")
        if payload.action == "confirm":
            return indicators_repo.update_indicator(db, row, verification_status="confirmed")
        if payload.action == "reject":
            return indicators_repo.update_indicator(db, row, verification_status="rejected")
        return indicators_repo.update_indicator(db, row, value=payload.value)
    raise HTTPException(status_code=400, detail=f"未知类型: {type_}")


@router.patch("/{type_}/{item_id}")
def patch_moderation(type_: str, item_id: int, payload: ModerationPatch,
                     db: Session = Depends(get_db)) -> dict:
    if payload.action not in {"confirm", "reject", "edit"}:
        raise HTTPException(status_code=400, detail="action 必须为 confirm/reject/edit")
    if type_ not in {"timeline", "weapon", "stance", "indicator"}:
        raise HTTPException(status_code=400,
                            detail="type 必须为 timeline/weapon/stance/indicator")
    row = _apply(db, type_, item_id, payload)
    from app.api.routes_boards import _event_out, _indicator_out, _stance_out, _weapon_out

    if type_ == "timeline":
        return _event_out(row)
    if type_ == "weapon":
        return _weapon_out(row)
    if type_ == "stance":
        return _stance_out(row)
    return _indicator_out(row)
