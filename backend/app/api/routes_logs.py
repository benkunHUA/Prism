from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories import logs as repo

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
def list_logs(limit: int = Query(default=50, le=200),
              db: Session = Depends(get_db)) -> dict:
    items = []
    for log in repo.list_logs(db, limit=limit):
        task = None
        if log.task_id:
            from app.repositories import tasks as tasks_repo

            task = tasks_repo.get_task(db, log.task_id)
        items.append(
            {
                "id": log.id,
                "task_id": log.task_id,
                "task_name": task.name if task else None,
                "started_at": log.started_at.isoformat(),
                "finished_at": log.finished_at.isoformat() if log.finished_at else None,
                "status": log.status,
                "fetched_count": log.fetched_count,
                "new_count": log.new_count,
                "error": log.error,
            }
        )
    return {"items": items}
