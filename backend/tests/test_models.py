from app.core.database import Base, make_engine, make_session_factory
from app.models.entities import Article, Category, Source, SourceCategory


def _engine(tmp_path):
    engine = make_engine(str(tmp_path / "t.db"))
    Base.metadata.create_all(engine)
    return engine


def test_source_categories_and_article(tmp_path):
    engine = _engine(tmp_path)
    factory = make_session_factory(engine)
    with factory() as db:
        src = Source(name="Reuters", url="https://example.com/feed", feed_type="rss")
        src.source_categories = [
            SourceCategory(category=Category.economy.value),
            SourceCategory(category=Category.finance.value),
        ]
        db.add(src)
        db.flush()
        art = Article(source_id=src.id, category=Category.economy.value, url="https://example.com/a/1",
                      title="T", dedupe_hash="h1")
        db.add(art)
        db.commit()
        assert src.id and art.id


def test_delete_source_keeps_article_with_null_source(tmp_path):
    engine = _engine(tmp_path)
    factory = make_session_factory(engine)
    with factory() as db:
        src = Source(name="S", url="https://example.com/s", feed_type="rss")
        db.add(src)
        db.flush()
        art = Article(source_id=src.id, category=Category.politics.value, url="https://example.com/s/a",
                      title="T", dedupe_hash="h2")
        db.add(art)
        db.commit()
        db.delete(src)
        db.commit()
        assert db.get(Article, art.id).source_id is None
    engine.dispose()
