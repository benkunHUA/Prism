from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.models.entities import Category
from app.repositories import analyses, articles, logs, sources, tasks
from app.services.flow import run_task_flow
from app.services.llm import ChatProvider

FIXTURE = Path(__file__).parent / "data" / "fixture_feed.xml"


class FakeProvider(ChatProvider):
    name = "fake"

    def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
        return "- **事件**：Fed moves\n  **影响**：关注利率路径\n  **来源**：Fixture"


def _feed_client():
    feed = FIXTURE.read_bytes()
    return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=feed)))


def _setup(db):
    sources.create_source(
        db, name="Fixture", url="https://example.com/rss", feed_type="rss", lang="en",
        categories=[Category.economy.value, Category.finance.value],
    )
    return tasks.create_task(db, name="采集", kind="collect", category=None, cron="0 */4 * * *")


def test_collect_flow_writes_log_and_brief(db):
    from app.core.config import Settings

    task = _setup(db)
    settings = Settings(_env_file=None)
    result = run_task_flow(
        db, task, client=_feed_client(),
        provider=FakeProvider(settings), settings=settings,
    )
    assert result["status"] == "success"
    assert result["new"] == 2
    assert logs.list_logs(db)[0].status == "success"
    assert len(analyses.list_analyses(db, kind="brief")) == 2  # economy + finance 各有快讯


def test_analyze_flow_creates_daily(db):
    from app.core.config import Settings

    _setup(db)
    settings = Settings(_env_file=None)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    articles.insert_articles(db, [
        dict(source_id=None, category="economy", url="https://example.com/x",
             title="X", summary="s", content_text="c" * 500,
             published_at=now, lang="en", dedupe_hash="hx"),
    ])
    task = tasks.create_task(db, name="分析", kind="analyze", category="economy", cron="0 8 * * *")
    result = run_task_flow(db, task, provider=FakeProvider(settings), settings=settings)
    assert result["status"] == "success"
    daily = analyses.latest_analysis(db, "economy", "daily")
    assert daily is not None and daily.status == "success"


def test_failed_provider_marks_partial(db):
    from app.core.config import Settings

    class BoomProvider(FakeProvider):
        def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
            raise RuntimeError("boom")

    _setup(db)
    settings = Settings(_env_file=None)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    articles.insert_articles(db, [
        dict(source_id=None, category="military", url="https://example.com/m",
             title="M", summary="s", content_text="c" * 500,
             published_at=now, lang="en", dedupe_hash="hm"),
    ])
    task = tasks.create_task(db, name="分析", kind="analyze", category="military", cron="0 8 * * *")
    result = run_task_flow(db, task, provider=BoomProvider(settings), settings=settings)
    assert result["status"] == "failed"
    assert "military" in " ".join(result["errors"])
    assert logs.list_logs(db)[0].status == "failed"
