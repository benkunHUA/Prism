from app.api.serializers import article_out
from app.repositories import articles as articles_repo
from app.repositories import sources as sources_repo


def _one(db):
    src = sources_repo.create_source(db, name="S", url="https://example.com/feed",
                                     feed_type="rss", lang="en", categories=["politics"])
    articles_repo.insert_articles(db, [
        dict(source_id=src.id, category="politics", url="https://example.com/a",
             title="Title", summary="Summary", content_text="",
             published_at=None, lang="en", dedupe_hash="h1"),
    ])
    return articles_repo.list_articles(db)[0]


def test_article_out_carries_translations(db):
    article = _one(db)
    article.title_zh = "标题"
    article.summary_zh = "要点"
    db.commit()

    payload = article_out(article)

    assert payload["title_zh"] == "标题"
    assert payload["summary_zh"] == "要点"
    assert payload["title"] == "Title"  # 原文字段保持不变


def test_article_out_translation_is_null_when_missing(db):
    payload = article_out(_one(db))

    assert payload["title_zh"] is None
    assert payload["summary_zh"] is None
