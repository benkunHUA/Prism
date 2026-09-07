from sqlalchemy.orm import Session

from app.models.entities import RunLog, utcnow


def create_log(db: Session, task_id: int | None) -> RunLog:
    log = RunLog(task_id=task_id)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def finish_log(db: Session, log: RunLog, *, status: str,
               fetched_count: int = 0, new_count: int = 0,
               error: str | None = None) -> None:
    log.status = status
    log.fetched_count = fetched_count
    log.new_count = new_count
    log.error = error
    log.finished_at = utcnow()
    db.commit()


def list_logs(db: Session, limit: int = 50) -> list[RunLog]:
    return db.query(RunLog).order_by(RunLog.started_at.desc()).limit(limit).all()
