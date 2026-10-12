from datetime import datetime, timezone

from app.core.constants import ALL_CATEGORIES
from app.models.entities import Category
from app.repositories import article_regions as regions_repo
from app.repositories import articles as articles_repo
from app.repositories import sources as sources_repo


def _seed(client):
    with client.app.state.session_factory() as db:
        source = sources_repo.create_source(
            db, name="S", url="https://example.com/rss", feed_type="rss", lang="en",
            categories=[Category.politics.value, Category.finance.value],
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        articles_repo.insert_articles(db, [
            dict(source_id=source.id, category="politics", url="https://example.com/1",
                 title="中东议题", summary="s", content_text="", published_at=now,
                 lang="en", dedupe_hash="g1"),
            dict(source_id=source.id, category="finance", url="https://example.com/2",
                 title="红海运费", summary="s", content_text="", published_at=now,
                 lang="en", dedupe_hash="g2"),
            dict(source_id=source.id, category="finance", url="https://example.com/3",
                 title="无地区", summary="s", content_text="", published_at=now,
                 lang="en", dedupe_hash="g3"),
        ])
        by_hash = {a.dedupe_hash: a for a in articles_repo.list_articles(db)}
        regions_repo.write_regions(db, article_id=by_hash["g1"].id, codes=["il", "gaza"])
        regions_repo.write_regions(db, article_id=by_hash["g2"].id, codes=["il"])


def test_dashboard_geo_aggregates_by_region_and_category(client):
    _seed(client)
    body = client.get("/api/dashboard/geo?window=24h").json()

    assert body["window"] == "24h"
    assert body["total"] == 3
    assert body["untagged"] == 1
    assert body["regions"][0]["code"] == "il"  # 按 count 倒序

    israel = next(r for r in body["regions"] if r["code"] == "il")
    assert israel["name"] == "以色列"
    assert israel["count"] == 2
    assert israel["by_category"]["politics"] == 1
    assert israel["by_category"]["finance"] == 1
    assert israel["by_category"]["military"] == 0

    gaza = next(r for r in body["regions"] if r["code"] == "gaza")
    assert gaza["count"] == 1 and gaza["by_category"]["politics"] == 1


def test_dashboard_geo_rejects_unknown_window(client):
    assert client.get("/api/dashboard/geo?window=1h").status_code == 422


def test_region_articles_endpoint(client):
    _seed(client)
    body = client.get("/api/regions/il/articles").json()
    assert body["name"] == "以色列"
    assert len(body["items"]) == 2

    finance_only = client.get("/api/regions/il/articles?category=finance").json()
    assert [item["title"] for item in finance_only["items"]] == ["红海运费"]
    assert client.get("/api/regions/nowhere/articles").status_code == 404


def test_dashboard_geo_by_category_keys_equal_all_categories(client):
    _seed(client)
    regions = {
        r["code"]: r
        for r in client.get("/api/dashboard/geo?window=24h").json()["regions"]
    }
    for code in ("il", "gaza"):
        assert set(regions[code]["by_category"]) == set(ALL_CATEGORIES)
    assert regions["gaza"]["by_category"]["finance"] == 0


def test_region_articles_limit_bounds(client):
    assert client.get("/api/regions/il/articles?limit=-1").status_code == 422
    assert client.get("/api/regions/il/articles?limit=101").status_code == 422
