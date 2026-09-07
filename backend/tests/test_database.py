from sqlalchemy import text

from app.core.database import Base, make_engine, make_session_factory


def test_wal_and_foreign_keys(tmp_path):
    db_file = tmp_path / "t.db"
    engine = make_engine(str(db_file))
    with engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        fk = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert mode == "wal"
        assert fk == 1
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        assert session.execute(text("SELECT 1")).scalar() == 1
    engine.dispose()


def test_memory_engine():
    engine = make_engine(":memory:")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1
    engine.dispose()
