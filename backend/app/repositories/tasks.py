from sqlalchemy.orm import Session

from app.models.entities import Task, utcnow


def list_tasks(db: Session) -> list[Task]:
    return db.query(Task).order_by(Task.id).all()


def get_task(db: Session, task_id: int) -> Task | None:
    return db.get(Task, task_id)


def create_task(db: Session, *, name: str, kind: str,
                category: str | None, cron: str, enabled: bool = True) -> Task:
    task = Task(name=name, kind=kind, category=category, cron=cron, enabled=enabled)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task: Task, *, name: str | None = None,
                kind: str | None = None, category: str | None = None,
                cron: str | None = None, enabled: bool | None = None) -> Task:
    if name is not None:
        task.name = name
    if kind is not None:
        task.kind = kind
    if category is not None:
        task.category = category
    if cron is not None:
        task.cron = cron
    if enabled is not None:
        task.enabled = enabled
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task: Task) -> None:
    db.delete(task)
    db.commit()


def set_task_run(db: Session, task: Task, *, ok: bool) -> None:
    task.last_run_at = utcnow()
    db.commit()
