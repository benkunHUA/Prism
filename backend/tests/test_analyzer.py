from datetime import datetime, timedelta, timezone

import pytest

from app.models.entities import Category
from app.repositories import analyses, articles, sources
from app.services.analyzer import generate_brief, generate_daily
from app.services.llm import ChatProvider


class FakeProvider(ChatProvider):
    name = "fake"

    def __init__(self, settings, text: str):
        super().__init__(settings)
        self.text = text

    def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
        return self.text


class CapturingProvider(FakeProvider):
    def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
        self.last_prompt = messages[-1]["content"]
        self.last_max_tokens = max_tokens
        return self.text


def _seed_material(db):
    src = sources.create_source(
        db, name="S", url="https://example.com/rss", feed_type="rss", lang="en",
        categories=[Category.economy.value],
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    articles.insert_articles(db, [
        dict(source_id=src.id, category="economy", url="https://example.com/a",
             title="Fed moves", summary="summary a", content_text="long body a" * 50,
             published_at=now, lang="en", dedupe_hash="ha"),
        dict(source_id=src.id, category="economy", url="https://example.com/b",
             title="ECB moves", summary="summary b", content_text="long body b" * 50,
             published_at=now, lang="en", dedupe_hash="hb"),
    ])
    return now


def test_generate_brief_stores_markdown(db):
    from app.core.config import Settings

    now = _seed_material(db)
    settings = Settings(_env_file=None)
    provider = FakeProvider(settings, "- **事件**：Fed moves\n  **影响**：中\n  **来源**：S")
    result = generate_brief(db, "economy", provider, settings, since=now - timedelta(hours=1))
    assert result is not None and result.kind == "brief"
    assert "Fed moves" in result.content_md


def test_generate_daily_links_only_real_citations(db):
    from app.core.config import Settings

    now = _seed_material(db)
    settings = Settings(_env_file=None)
    md = (
        "## 要点速览\n- 关键结论一\n\n## 重大事件与事实\n事件描述\n\n"
        "## 资料来源\n- 1 S · Fed moves\n- 2 S · ECB moves\n- 9 Fake · Not real"
    )
    provider = FakeProvider(settings, md)
    result = generate_daily(db, "economy", provider, settings, until=now + timedelta(seconds=5))
    assert result is not None and result.kind == "daily"
    assert result.status == "success"
    linked = {link.article_id for link in analyses.get_analysis(db, result.id).article_links}
    material_ids = {
        a.id for a in articles.articles_for_analysis(
            db, "economy", now - timedelta(hours=24), now + timedelta(seconds=5)
        )
    }
    assert linked == material_ids and len(linked) == 2


def test_generate_daily_empty_returns_none(db):
    from app.core.config import Settings

    settings = Settings(_env_file=None)
    provider = FakeProvider(settings, "irrelevant")
    assert generate_daily(db, "military", provider, settings) is None


def test_daily_title_and_prompt_follow_board_spec(db):
    from app.core.config import Settings

    now = _seed_material(db)
    settings = Settings(_env_file=None)
    md = "## 数据要点\n- 结论\n\n## 资料来源\n- 1 S · Fed moves"
    provider = CapturingProvider(settings, md)
    result = generate_daily(db, "economy", provider, settings, until=now + timedelta(seconds=5))
    assert result is not None
    assert result.title.startswith("宏观与政策简报 · ")
    assert "## 数据要点" in provider.last_prompt
    assert "## 资产表现" not in provider.last_prompt


def test_brief_title_uses_board_label(db):
    from app.core.config import Settings

    now = _seed_material(db)
    settings = Settings(_env_file=None)
    provider = FakeProvider(settings, "- **事件**：x\n  **影响**：y\n  **来源**：S")
    result = generate_brief(db, "economy", provider, settings, since=now - timedelta(hours=1))
    assert result is not None and result.title.startswith("经济快讯 ")


def test_empty_llm_output_is_not_stored(db):
    from app.core.config import Settings
    from app.repositories import analyses

    now = _seed_material(db)
    settings = Settings(_env_file=None)
    provider = FakeProvider(settings, "   ")
    with pytest.raises(RuntimeError, match="为空"):
        generate_daily(db, "economy", provider, settings, until=now + timedelta(seconds=5))
    assert analyses.list_analyses(db, category="economy", kind="daily") == []


def test_daily_uses_configured_token_budget(db):
    from app.core.config import Settings

    now = _seed_material(db)
    settings = Settings(_env_file=None, llm_daily_max_tokens=12345)
    provider = CapturingProvider(settings, "## 数据要点\n内容\n\n## 资料来源\n- 1 S · Fed moves")
    generate_daily(db, "economy", provider, settings, until=now + timedelta(seconds=5))
    assert provider.last_max_tokens == 12345


def test_parse_citation_ids_accepts_bracket_and_plain_numbers():
    from app.services.analyzer import _parse_citation_ids

    md = (
        "## 资料来源\n"
        "- [1] 站点 · 标题一\n"
        "- 2. 站点 · 标题二\n"
        "- 3、站点 · 标题三\n"
        "- [99] 越界条目\n"
        "补充说明：无编号的行忽略\n"
    )
    assert _parse_citation_ids(md, 5) == [1, 2, 3]
