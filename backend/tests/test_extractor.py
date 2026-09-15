import json
from datetime import datetime, timezone

from app.repositories import articles, indicators, sources, stances, timeline, weapons
from app.services.extraction.extractor import extract_article
from app.services.llm import ChatProvider


class FakeProvider(ChatProvider):
    name = "fake"

    def __init__(self, settings, payload_by_category):
        super().__init__(settings)
        self.payload_by_category = payload_by_category

    def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
        category = self.payload_by_category["category"]
        return json.dumps(self.payload_by_category[category], ensure_ascii=False)


def _make_article(db, category, url):
    src = sources.create_source(db, name="S", url=f"https://example.com/{category}",
                                feed_type="rss", lang="en", categories=[category])
    articles.insert_articles(db, [dict(source_id=src.id, category=category, url=url,
                                       title=f"T-{category}", summary="s", content_text="正文",
                                       published_at=datetime.now(timezone.utc).replace(tzinfo=None),
                                       lang="en", dedupe_hash=f"h-{category}")])
    return articles.list_articles(db, category=category)[0]


def test_extract_politics_writes_events_and_stances(db):
    from app.core.config import Settings

    art = _make_article(db, "politics", "https://example.com/p1")
    provider = FakeProvider(Settings(_env_file=None), {
        "category": "politics",
        "politics": {
            "events": [{"subtype": "立法与投票", "actor": "欧盟议会", "region": "欧盟",
                        "occurred_at": "2026-09-08T09:00:00", "summary": "修正案表决通过",
                        "importance": "high"}],
            "stances": [{"topic": "对华", "actor": "美国商务部", "stance_text": "名单扩大",
                         "tone": "趋严", "stated_at": "2026-09-08T08:00:00"}],
        },
    })
    stats = extract_article(db, art, provider, Settings(_env_file=None))
    assert stats["created"] == 2
    events = timeline.list_events(db, category="politics")
    assert events[0].verification_status == "confirmed"  # 表决通过 → 自动确认
    assert stances.list_stances(db)[0].verification_status == "draft"


def test_extract_military_writes_draft_weapon(db):
    from app.core.config import Settings

    art = _make_article(db, "military", "https://example.com/m1")
    provider = FakeProvider(Settings(_env_file=None), {
        "category": "military",
        "military": {
            "weapons": [{"name": "第六代验证机", "origin": "美国", "weapon_type": "战斗机",
                         "params_text": "飞翼布局", "lifecycle_status": "研发"}],
            "conflicts": [{"subtype": "冲突进展", "actor": "乌军", "region": "俄乌",
                           "occurred_at": "2026-09-08T06:00:00", "summary": "击退多方向进攻",
                           "importance": "high"}],
        },
    })
    extract_article(db, art, provider, Settings(_env_file=None))
    assert weapons.list_weapons(db)[0].verification_status == "draft"
    assert timeline.list_events(db, category="military")[0].verification_status == "draft"


def test_extract_economy_writes_confirmed_indicator(db):
    from app.core.config import Settings

    art = _make_article(db, "economy", "https://example.com/e1")
    provider = FakeProvider(Settings(_env_file=None), {
        "category": "economy",
        "economy": {
            "indicators": [{"indicator": "CPI", "region": "中国", "period": "2026-08",
                            "value": 0.4, "unit": "%", "previous": 0.5, "forecast": 0.6,
                            "released_at": "2026-09-08T09:30:00"}],
            "policies": [],
        },
    })
    extract_article(db, art, provider, Settings(_env_file=None))
    assert indicators.list_indicators(db)[0].verification_status == "confirmed"
