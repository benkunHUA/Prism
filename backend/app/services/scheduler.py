from __future__ import annotations

import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models.entities import Task
from app.repositories import tasks as tasks_repo
from app.services.flow import run_task_flow


class SchedulerManager:
    """启动后每分钟与 tasks 表同步；作业带进程内锁，防止手动/定时重入。"""

    def __init__(self, session_factory: sessionmaker, settings: Settings) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.scheduler = BackgroundScheduler(timezone="UTC")
        self._lock = threading.Lock()

    def start(self) -> None:
        self.scheduler.add_job(
            self.sync, "interval", minutes=1, id="sync-tasks",
            replace_existing=True, max_instances=1, coalesce=True,
        )
        self.scheduler.start()
        self.sync()

    def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)

    def sync(self) -> None:
        with self.session_factory() as db:
            tasks = tasks_repo.list_tasks(db)
            enabled = {t.id for t in tasks if t.enabled}
            for task in tasks:
                job_id = f"task-{task.id}"
                if task.id in enabled:
                    trigger = CronTrigger.from_crontab(task.cron, timezone="UTC")
                    self.scheduler.add_job(
                        self._guarded, trigger, args=[task.id],
                        id=job_id, replace_existing=True,
                        max_instances=1, coalesce=True,
                    )
                elif self.scheduler.get_job(job_id):
                    self.scheduler.remove_job(job_id)
            # 删除已不存在的任务对应作业
            for job in list(self.scheduler.get_jobs()):
                if job.id.startswith("task-") and int(job.id.split("-", 1)[1]) not in enabled:
                    self.scheduler.remove_job(job.id)
            # 回写 next_run_at（去时区）
            for task in tasks:
                job = self.scheduler.get_job(f"task-{task.id}")
                if job and job.next_run_time:
                    task.next_run_at = job.next_run_time.replace(tzinfo=None)
            db.commit()

    def _guarded(self, task_id: int) -> None:
        with self._lock:
            with self.session_factory() as db:
                task: Task | None = tasks_repo.get_task(db, task_id)
                if task and task.enabled:
                    run_task_flow(db, task, settings=self.settings)
