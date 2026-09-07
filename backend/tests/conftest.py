import pytest


@pytest.fixture()
def db(tmp_path):
    from app.core.database import Base, make_engine, make_session_factory

    engine = make_engine(str(tmp_path / "t.db"))
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    session = factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    from fastapi.testclient import TestClient

    app = create_app()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()
