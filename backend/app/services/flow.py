from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.constants import ALL_CATEGORIES
from app.models.entities import Task
from app.repositories import articles as articles_repo
from app.repositories import logs as logs_repo
from app.repositories import tasks as tasks_repo
from app.services import analyzer
from app.services.collector import collect_new
from app.services.llm import ChatProvider, get_provider


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _task_categories(task: Task) -> list[str]:
    return [task.category] if task.category else ALL_CATEGORIES


def run_task_flow(db: Session, task: Task, *, client=None,
                  provider: ChatProvider | None = None,
                  settings: Settings | None = None) -> dict:
    """执行单个任务，全程写 run_logs；返回状态摘要。"""
    settings = settings or Settings(_env_file=None)
    started = _utcnow()
    log = logs_repo.create_log(db, task.id)
    fetched = new = 0
    errors: list[str] = []
    try:
        if task.kind == "collect":
            result = collect_new(db, category=task.category, client=client, settings=settings)
            fetched += result["fetched"]
            new += result["new"]
            errors.extend(result["errors"])
            brief_categories = _task_categories(task)
            prov = provider or get_provider(settings)
            since = started - timedelta(hours=6)
            for cat in brief_categories:
                if articles_repo.count_new_since(db, cat, since):
                    try:
                        analyzer.generate_brief(db, cat, prov, settings, since=since)
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"{cat} 快讯失败: {exc}")
        elif task.kind == "analyze":
            prov = provider or get_provider(settings)
            for cat in _task_categories(task):
                try:
                    analyzer.generate_daily(db, cat, prov, settings)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{cat} 每日分析失败: {exc}")
        else:
            raise ValueError(f"未知任务类型: {task.kind}")
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))
    status = "success" if not errors else ("partial" if new else "failed")
    error_msg = "；".join(errors)[:4000] or None
    logs_repo.finish_log(
        db, log, status=status, fetched_count=fetched, new_count=new, error=error_msg
    )
    tasks_repo.set_task_run(db, task, ok=status != "failed")
    return {"task_id": task.id, "status": status, "fetched": fetched, "new": new, "errors": errors}
