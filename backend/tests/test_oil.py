from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.core.config import Settings
from app.models.entities import Category
from app.repositories import articles, sources
from app.services.analyzer import generate_daily
from app.services.llm import ChatProvider
from app.services.oil import is_oil_related, prioritize_oil_materials


class CapturingProvider(ChatProvider):
    name = "capturing"

    def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
        self.prompt = messages[-1]["content"]
        return "## 资产表现\n内容\n\n## 资料来源\n- 1 Test · Crude oil rises"


def _seed_articles(db):
    src = sources.create_source(
        db, name="Test", url="https://example.com/rss", feed_type="rss", lang="en",
        categories=[Category.finance.value],
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    articles.insert_articles(db, [
        dict(source_id=src.id, category="finance", url="https://example.com/oil",
             title="Crude oil rises as OPEC cuts supply", summary="Brent and WTI gain",
             content_text="barrel " * 100, published_at=now - timedelta(hours=5),
             lang="en", dedupe_hash="oil"),
        dict(source_id=src.id, category="finance", url="https://example.com/a",
             title="Stocks edge higher", summary="Wall Street", content_text="market " * 100,
             published_at=now - timedelta(hours=1), lang="en", dedupe_hash="a"),
        dict(source_id=src.id, category="finance", url="https://example.com/b",
             title="Bond yields fall", summary="Treasuries", content_text="rates " * 100,
             published_at=now - timedelta(hours=2), lang="en", dedupe_hash="b"),
        dict(source_id=src.id, category="finance", url="https://example.com/c",
             title="Bank earnings beat", summary="Lenders", content_text="bank " * 100,
             published_at=now - timedelta(hours=3), lang="en", dedupe_hash="c"),
    ])
    fetched_hours = {"oil": 5, "a": 1, "b": 2, "c": 3}
    for row in articles.list_articles(db, category="finance"):
        row.fetched_at = now - timedelta(hours=fetched_hours[row.dedupe_hash])
    db.commit()
    return now


def test_oil_matcher_uses_english_and_chinese_terms():
    class Row:
        title = "Brent crude climbs"
        summary = ""
        content_text = ""
        source = None

    class ChineseRow:
        title = "国际原油价格上涨"
        summary = ""
        content_text = ""
        source = None

    assert is_oil_related(Row()) is True
    assert is_oil_related(ChineseRow()) is True


def test_finance_analysis_keeps_an_oil_slot(db):
    now = _seed_articles(db)
    settings = Settings(_env_file=None, top_articles_per_analysis=2)
    provider = CapturingProvider(settings)

    generate_daily(db, "finance", provider, settings, until=now + timedelta(seconds=5))

    assert "Crude oil rises" in provider.prompt
    assert "Stocks edge higher" in provider.prompt


def test_prioritize_oil_materials_respects_limit(db):
    now = _seed_articles(db)
    rows = articles.articles_for_analysis(
        db, "finance", now - timedelta(hours=24), now + timedelta(seconds=5), limit=10
    )

    selected = prioritize_oil_materials(rows, 2)

    assert len(selected) == 2
    assert any("Crude oil" in row.title for row in selected)


def test_oil_reserve_never_exceeds_limit():
    rows = [
        SimpleNamespace(
            id=index,
            title="Crude oil update",
            summary="",
            content_text="",
            source=None,
            fetched_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        for index in range(4)
    ]

    assert len(prioritize_oil_materials(rows, 2)) == 2
