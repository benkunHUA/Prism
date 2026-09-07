from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(db_path: str) -> Engine:
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{db_path}"
    else:
        url = "sqlite://"
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
