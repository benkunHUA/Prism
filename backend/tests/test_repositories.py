from datetime import datetime, timezone

from app.models.entities import Analysis, Category, Source
from app.repositories import analyses, articles, logs, sources, tasks


def _source(db) -> Source:
    return sources.create_source(
        db, name="S", url="https://example.com/rss", feed_type="rss", lang="en",
        categories=[Category.economy.value],
    )


def test_source_crud_and_health_degrade(db):
    src = _source(db)
    assert [c.category for c in src.source_categories] == ["economy"]
    sources.update_source(db, src, categories=["economy", "finance"])
    assert {c.category for c in src.source_categories} == {"economy", "finance"}
    for i in range(3):
        sources.set_source_health(db, src, ok=False, error=f"err{i}")
    db.refresh(src)
    assert src.enabled is False
    assert src.error_count == 3
    sources.set_source_health(db, src, ok=True)
    db.refresh(src)
    assert src.enabled is True and src.error_count == 0


def test_article_insert_dedupes(db):
    src = _source(db)
    items = [
        dict(source_id=src.id, category="economy", url="https://example.com/a?utm_source=x",
             title="Update: Fed Hikes Rates", summary="s", content_text="", published_at=None,
             lang="en", dedupe_hash="h1"),
        dict(source_id=src.id, category="economy", url="https://example.com/a",
             title="Fed hikes rates", summary="s2", content_text="", published_at=None,
             lang="en", dedupe_hash="h1"),
        dict(source_id=src.id, category="economy", url="https://example.com/b",
             title="New Item", summary="s3", content_text="", published_at=None,
             lang="en", dedupe_hash="h2"),
    ]
    assert articles.insert_articles(db, items) == 2
    assert articles.insert_articles(db, items) == 0
    assert len(articles.list_articles(db, category="economy")) == 2


def test_analysis_and_links(db):
    src = _source(db)
    articles.insert_articles(db, [dict(source_id=src.id, category="economy", url="https://example.com/x",
                                       title="X", summary="", content_text="", published_at=None,
                                       lang="en", dedupe_hash="hx")])
    art = articles.list_articles(db)[0]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    an = analyses.create_analysis(
        db, kind="daily", category="economy", title="T", content_md="# T",
        period_start=now, period_end=now, model="fake",
    )
    analyses.link_articles(db, an, [art.id])
    assert analyses.get_analysis(db, an.id).article_links[0].article_id == art.id
    assert analyses.latest_analysis(db, "economy", "daily").id == an.id


def test_tasks_and_logs(db):
    t = tasks.create_task(db, name="采集", kind="collect", category=None, cron="0 */4 * * *")
    tasks.set_task_run(db, t, ok=True)
    db.refresh(t)
    assert t.last_run_at is not None
    lg = logs.create_log(db, t.id)
    logs.finish_log(db, lg, status="success", fetched_count=3, new_count=2)
    db.refresh(lg)
    assert lg.status == "success" and lg.new_count == 2
    assert logs.list_logs(db, limit=5)[0].id == lg.id
