# backend/tests/test_article_regions.py
from datetime import datetime, timedelta, timezone

from app.repositories import article_regions as regions_repo
from app.repositories import articles as articles_repo
from app.repositories import sources as sources_repo


def _seed_article(db, *, category: str, url: str, dedupe: str, hours_ago: int = 0):
    source = sources_repo.create_source(
        db, name=f"S-{dedupe}", url=f"https://example.com/{dedupe}",
        feed_type="rss", lang="en", categories=[category],
    )
    when = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours_ago)
    articles_repo.insert_articles(db, [
        dict(source_id=source.id, category=category, url=url, title=f"T-{dedupe}",
             summary="s", content_text="", published_at=when, lang="en", dedupe_hash=dedupe),
    ])
    article = next(a for a in articles_repo.list_articles(db) if a.dedupe_hash == dedupe)
    article.fetched_at = when
    db.commit()
    return article


def test_write_regions_dedupes_and_skips_existing(db):
    article = _seed_article(db, category="politics", url="https://example.com/a1", dedupe="a1")
    assert regions_repo.write_regions(db, article_id=article.id,
                                      codes=["us", "gaza", "us", ""]) == 2
    assert regions_repo.codes_for_article(db, article.id) == {"us", "gaza"}
    assert regions_repo.write_regions(db, article_id=article.id, codes=["us"]) == 0


def test_count_by_region_and_untagged_respect_window(db):
    fresh = _seed_article(db, category="military", url="https://example.com/a2", dedupe="a2")
    stale = _seed_article(db, category="military", url="https://example.com/a3",
                          dedupe="a3", hours_ago=48)
    regions_repo.write_regions(db, article_id=fresh.id, codes=["il", "gaza"])
    regions_repo.write_regions(db, article_id=stale.id, codes=["ua"])

    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    rows = {(code, cat): count for code, cat, count in regions_repo.count_by_region(db, since)}
    assert rows[("il", "military")] == 1
    assert rows[("gaza", "military")] == 1
    assert ("ua", "military") not in rows  # 48 小时前的文章被窗口排除
    assert regions_repo.untagged_count(db, since) == 0

    _seed_article(db, category="military", url="https://example.com/a4", dedupe="a4")
    assert regions_repo.untagged_count(db, since) == 1
    assert regions_repo.article_ids_with_regions(db, [fresh.id, stale.id]) == {fresh.id, stale.id}


def test_list_articles_by_region_filters_category(db):
    first = _seed_article(db, category="politics", url="https://example.com/b1", dedupe="b1")
    second = _seed_article(db, category="finance", url="https://example.com/b2", dedupe="b2")
    regions_repo.write_regions(db, article_id=first.id, codes=["us"])
    regions_repo.write_regions(db, article_id=second.id, codes=["us"])
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)

    all_items = regions_repo.list_articles_by_region(db, code="us", since=since)
    assert {a.id for a in all_items} == {first.id, second.id}
    finance_only = regions_repo.list_articles_by_region(db, code="us", since=since,
                                                       category="finance")
    assert [a.id for a in finance_only] == [second.id]
