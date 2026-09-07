from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.models.entities import Category
from app.repositories import articles, sources
from app.services.collector import collect_new

FIXTURE = Path(__file__).parent / "data" / "fixture_feed.xml"


def _mock_client():
    feed = FIXTURE.read_bytes()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=feed)
    )
    return httpx.Client(transport=transport)


def test_collect_inserts_and_dedupes(db):
    src = sources.create_source(
        db, name="Fixture", url="https://example.com/rss", feed_type="rss", lang="en",
        categories=[Category.economy.value, Category.finance.value],
    )
    result = collect_new(db, client=_mock_client())
    assert result["new"] == 2
    assert result["errors"] == []
    db.refresh(src)
    assert src.last_ok_at is not None and src.error_count == 0
    # 二次运行全部去重
    result2 = collect_new(db, client=_mock_client())
    assert result2["new"] == 0
    # 经济板块能看到该源文章（多板块覆盖查询）
    assert len(articles.list_articles(db, category="economy")) == 2
    # 分析选材也命中
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    mats = articles.articles_for_analysis(
        db, "economy", now - timedelta(hours=1), now + timedelta(seconds=5)
    )
    assert len(mats) == 2


def test_collect_marks_failing_source(db):
    src = sources.create_source(
        db, name="Broken", url="https://example.com/broken", feed_type="rss", lang="en",
        categories=[Category.politics.value],
    )

    def _fail(request):  # noqa: ANN001
        raise httpx.ConnectError("boom", request=request)

    client = httpx.Client(transport=httpx.MockTransport(_fail))
    result = collect_new(db, client=client)
    assert result["errors"] and result["new"] == 0
    db.refresh(src)
    assert src.error_count == 1 and src.enabled is True
