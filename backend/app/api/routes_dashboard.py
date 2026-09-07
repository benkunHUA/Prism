from datetime import datetime, timezone

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.constants import ALL_CATEGORIES
from app.repositories import analyses as analyses_repo
from app.repositories import articles as articles_repo
from app.repositories import sources as sources_repo
from app.repositories import tasks as tasks_repo

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _today_start() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _next_run_for(task) -> datetime | None:
    if task.next_run_at:
        return task.next_run_at
    trigger = CronTrigger.from_crontab(task.cron, timezone="UTC")
    fire = trigger.get_next_fire_time(None, datetime.now(timezone.utc))
    return fire.replace(tzinfo=None) if fire else None


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    since = _today_start()
    sources = sources_repo.list_sources(db)
    healthy = sum(1 for s in sources if s.enabled and s.error_count == 0)
    enabled = sum(1 for s in sources if s.enabled)
    next_run = min(
        (r for r in (_next_run_for(t) for t in tasks_repo.list_tasks(db) if t.enabled) if r),
        default=None,
    )
    return {
        "today_articles": articles_repo.count_all_since(db, since),
        "today_analyses": analyses_repo.count_daily_since(db, since),
        "source_health": {"healthy": healthy, "enabled": enabled},
        "next_run_at": next_run.isoformat() if next_run else None,
        "categories": ALL_CATEGORIES,
    }
