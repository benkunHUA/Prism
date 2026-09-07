from app.core.config import Settings
from app.core.database import Base, make_engine, make_session_factory
from app.repositories import tasks as tasks_repo
from app.services.scheduler import SchedulerManager


def test_sync_registers_and_removes_jobs(tmp_path):
    engine = make_engine(str(tmp_path / "s.db"))
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as db:
        task = tasks_repo.create_task(db, name="年度", kind="collect", category=None, cron="0 0 1 1 *")
        task_id = task.id
    settings = Settings(_env_file=None, scheduler_enabled=True)
    mgr = SchedulerManager(factory, settings)
    mgr.start()
    try:
        job = mgr.scheduler.get_job(f"task-{task_id}")
        assert job is not None
        assert mgr.scheduler.get_job("sync-tasks") is not None
        with factory() as db:
            task = tasks_repo.get_task(db, task_id)
            tasks_repo.update_task(db, task, enabled=False)
        mgr.sync()
        assert mgr.scheduler.get_job(f"task-{task_id}") is None
    finally:
        mgr.shutdown()
        engine.dispose()
