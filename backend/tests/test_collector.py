from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from types import SimpleNamespace

import httpx

from app.core.config import Settings
from app.models.entities import Category
from app.repositories import articles, sources
from app.services import collector
from app.services.collector import collect_new, fetch_source
from app.services.urlutil import absolute_url

FIXTURE = Path(__file__).parent / "data" / "fixture_feed.xml"


def _mock_client():
    feed = FIXTURE.read_bytes()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=feed)
    )
    return httpx.Client(transport=transport)


def _settings(max_feed_age_days: int = 30) -> Settings:
    return Settings(_env_file=None, max_feed_age_days=max_feed_age_days)


def test_collect_inserts_and_dedupes(db):
    src = sources.create_source(
        db, name="Fixture", url="https://example.com/rss", feed_type="rss", lang="en",
        categories=[Category.economy.value, Category.finance.value],
    )
    result = collect_new(db, client=_mock_client(), settings=_settings(365))
    assert result["new"] == 2
    assert result["errors"] == []
    db.refresh(src)
    assert src.last_ok_at is not None and src.error_count == 0
    # 二次运行全部去重
    result2 = collect_new(db, client=_mock_client(), settings=_settings(365))
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


RELATIVE_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Relative</title>
<item><title>EIA press release</title><link>/pressroom/releases/press590.php</link>
<description>short</description></item>
</channel></rss>
"""


def test_absolute_url_resolves_and_rejects_non_http():
    assert absolute_url("https://www.eia.gov/rss/press_rss.xml", "/pressroom/x.php") == (
        "https://www.eia.gov/pressroom/x.php"
    )
    assert absolute_url("https://www.eia.gov/rss/press_rss.xml", "mailto:a@b.com") == ""
    assert absolute_url("https://www.eia.gov/rss/press_rss.xml", "") == ""


def test_collect_resolves_relative_entry_links(db):
    src = sources.create_source(
        db, name="Relative", url="https://www.eia.gov/rss/press_rss.xml", feed_type="rss",
        lang="en", categories=[Category.economy.value],
    )
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=RELATIVE_FEED)))
    result = collect_new(db, client=client)
    assert result["errors"] == []
    rows = articles.list_articles(db, category="economy")
    assert len(rows) == 1
    # normalize_url 会去掉 www. 前缀，这里只断言链接已补全为绝对地址
    assert rows[0].url.startswith("https://eia.gov/pressroom/")
    db.refresh(src)
    assert src.error_count == 0


def test_fetch_source_degrades_on_unexpected_error(db):
    sources.create_source(
        db, name="Weird", url="https://example.com/rss", feed_type="rss", lang="en",
        categories=[Category.economy.value],
    )
    snap = type(
        "Snap", (), {"id": 1, "name": "Weird", "url": "https://example.com/rss",
                     "feed_type": "rss", "lang": "en", "categories": ["economy"]},
    )()

    class BoomClient:
        def get(self, *args, **kwargs):
            raise ValueError("unknown url type: '/relative'")

    from app.core.config import Settings

    items, error = fetch_source(snap, Settings(_env_file=None), BoomClient())
    assert items == [] and error and "ValueError" in error


def test_fetch_source_skips_entries_older_than_max_age():
    now = datetime.now(timezone.utc)
    stale = format_datetime(now - timedelta(days=60), usegmt=True)
    fresh = format_datetime(now - timedelta(days=1), usegmt=True)
    body = "x" * 240
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Mixed</title>
<item><title>Stale item</title><link>https://example.com/stale</link>
<description>{body}</description><pubDate>{stale}</pubDate></item>
<item><title>Fresh item</title><link>https://example.com/fresh</link>
<description>{body}</description><pubDate>{fresh}</pubDate></item>
</channel></rss>""".encode()
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=feed)))
    snap = SimpleNamespace(id=1, name="Mixed", url="https://example.com/rss", feed_type="rss",
                           lang="en", categories=["military"])

    items, error = fetch_source(snap, _settings(), client)

    assert error is None
    assert [item["title"] for item in items] == ["Fresh item"]


def test_collect_survives_source_level_exception(db, monkeypatch):
    sources.create_source(
        db, name="Exploding", url="https://example.com/rss", feed_type="rss", lang="en",
        categories=[Category.politics.value],
    )

    def _boom(*args, **kwargs):
        raise RuntimeError("unexpected boom")

    monkeypatch.setattr(collector, "fetch_source", _boom)
    result = collect_new(db, client=httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, content=RELATIVE_FEED)
    )))
    assert result["new"] == 0
    assert result["errors"] and "unexpected boom" in result["errors"][0]
