from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api import (  # noqa: F401
    routes_analyses,
    routes_articles,
    routes_boards,
    routes_categories,
    routes_dashboard,
    routes_geo,
    routes_health,
    routes_logs,
    routes_moderations,
    routes_sources,
    routes_tasks,
)
from app.api.security import BasicAuthMiddleware
from app.api.static_site import mount_spa
from app.core.config import Settings, get_settings
from app.core.database import make_engine, make_session_factory
from app.core.schema import ensure_schema
from app.repositories import logs as logs_repo
from app.services.scheduler import SchedulerManager
from app.services.seed import seed_defaults


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.db_path)
    ensure_schema(engine)
    session_factory = make_session_factory(engine)
    scheduler = SchedulerManager(session_factory, settings) if settings.scheduler_enabled else None

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        with session_factory() as db:
            seed_defaults(db, settings)
            logs_repo.fail_unfinished_runs(db)
        if scheduler:
            scheduler.start()
        yield
        if scheduler:
            scheduler.shutdown()
        engine.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.add_middleware(
        BasicAuthMiddleware, user=settings.auth_user, password=settings.auth_password
    )

    app.include_router(routes_health.router)
    app.include_router(routes_dashboard.router)
    app.include_router(routes_categories.router)
    app.include_router(routes_articles.router)
    app.include_router(routes_analyses.router)
    app.include_router(routes_sources.router)
    app.include_router(routes_tasks.router)
    app.include_router(routes_logs.router)
    app.include_router(routes_boards.router)
    app.include_router(routes_moderations.router)
    app.include_router(routes_geo.router)
    if settings.static_dir and Path(settings.static_dir).is_dir():
        mount_spa(app, settings.static_dir)
    return app


app = create_app()
