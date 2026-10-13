# backend/tests/test_geo_tag.py
from datetime import datetime, timedelta, timezone

from app.models.entities import Article
from app.repositories import article_regions as regions_repo
from app.repositories import articles as articles_repo
from app.repositories import sources as sources_repo
from app.services.geo_tag import backfill_source_regions


def _seed_article(db, *, url: str, dedupe: str, region: str = "") -> Article:
    source = sources_repo.create_source(
        db, name=f"S-{dedupe}", url=f"https://example.com/{dedupe}",
        feed_type="rss", lang="en", categories=["politics"],
    )
    source.region = region
    articles_repo.insert_articles(db, [
        dict(source_id=source.id, category="politics", url=url, title=f"T-{dedupe}",
             summary="s", content_text="", published_at=None, lang="en", dedupe_hash=dedupe),
    ])
    return db.query(Article).filter(Article.dedupe_hash == dedupe).one()


def _since() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)


def test_backfill_skips_articles_already_tagged(db):
    article = _seed_article(db, url="https://example.com/g1", dedupe="g1", region="gb")
    regions_repo.write_regions(db, article_id=article.id, codes=["il", "gaza"], source="llm")

    assert backfill_source_regions(db, [article]) == 0
    assert regions_repo.codes_for_article(db, article.id) == {"il", "gaza"}
    assert regions_repo.count_by_region(db, _since()) == [("gaza", "politics", 1),
                                                          ("il", "politics", 1)]


def test_backfill_leaves_untagged_when_source_has_no_region(db):
    without_region = _seed_article(db, url="https://example.com/g2", dedupe="g2")
    articles_repo.insert_articles(db, [
        dict(source_id=None, category="politics", url="https://example.com/g3",
             title="T-g3", summary="s", content_text="", published_at=None, lang="en",
             dedupe_hash="g3"),
    ])

    assert backfill_source_regions(db, [without_region]) == 0
    assert regions_repo.codes_for_article(db, without_region.id) == set()
    assert regions_repo.untagged_count(db, _since()) == 2  # 含 source_id=None 的文章


def test_backfill_drops_unknown_source_region_code(db):
    article = _seed_article(db, url="https://example.com/g4", dedupe="g4", region="uk-typo")

    assert backfill_source_regions(db, [article]) == 0
    assert regions_repo.codes_for_article(db, article.id) == set()
    assert regions_repo.untagged_count(db, _since()) == 1  # 幽灵行不得吞掉未标注计数


def test_backfill_normalizes_source_region_alias(db):
    article = _seed_article(db, url="https://example.com/g5", dedupe="g5", region="英国")

    assert backfill_source_regions(db, [article]) == 1
    assert regions_repo.codes_for_article(db, article.id) == {"gb"}
    assert regions_repo.untagged_count(db, _since()) == 0
