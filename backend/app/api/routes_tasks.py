from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.models.entities import Task
from app.repositories import tasks as repo
from app.services.flow import run_task_flow

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(pattern="^(collect|analyze)$")
    category: str | None = None
    cron: str = Field(min_length=5, max_length=100)
    enabled: bool = True


class TaskPatch(BaseModel):
    name: str | None = None
    kind: str | None = Field(default=None, pattern="^(collect|analyze)$")
    category: str | None = None
    cron: str | None = None
    enabled: bool | None = None


def _out(task: Task) -> dict:
    return {
        "id": task.id,
        "name": task.name,
        "kind": task.kind,
        "category": task.category,
        "cron": task.cron,
        "enabled": task.enabled,
        "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
        "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
    }


def _require(db: Session, task_id: int) -> Task:
    task = repo.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("")
def list_tasks(db: Session = Depends(get_db)) -> dict:
    return {"items": [_out(t) for t in repo.list_tasks(db)]}


@router.get("/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    return _out(_require(db, task_id))


@router.post("", status_code=201)
def create_task(payload: TaskIn, db: Session = Depends(get_db)) -> dict:
    task = repo.create_task(
        db, name=payload.name, kind=payload.kind,
        category=payload.category, cron=payload.cron, enabled=payload.enabled,
    )
    return _out(task)


@router.patch("/{task_id}")
def patch_task(task_id: int, payload: TaskPatch, db: Session = Depends(get_db)) -> dict:
    task = repo.update_task(
        db, _require(db, task_id), name=payload.name, kind=payload.kind,
        category=payload.category, cron=payload.cron, enabled=payload.enabled,
    )
    return _out(task)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)) -> None:
    repo.delete_task(db, _require(db, task_id))


@router.post("/{task_id}/run")
def run_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = _require(db, task_id)
    settings = get_settings()
    return run_task_flow(db, task, settings=settings)
