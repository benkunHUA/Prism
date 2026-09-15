from datetime import datetime, timezone

from app.models.entities import Category
from app.repositories import articles, indicators, snapshots, sources, stances, timeline, weapons


def _seed(client):
    with client.app.state.session_factory() as db:
        src = sources.create_source(db, name="S", url="https://example.com/rss",
                                    feed_type="rss", lang="en",
                                    categories=[Category.politics.value, Category.military.value,
                                                Category.economy.value, Category.finance.value])
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        articles.insert_articles(db, [
            dict(source_id=src.id, category="politics", url="https://example.com/a",
                 title="A", summary="s", content_text="", published_at=now,
                 lang="en", dedupe_hash="ha"),
        ])
        art = articles.list_articles(db, category="politics")[0]
        timeline.upsert_event(db, category="politics", subtype="外交与峰会",
                              actor="美日韩", region="亚太", summary="会晤",
                              verification_status="confirmed", article_id=art.id,
                              merge_key="e1")
        timeline.upsert_event(db, category="military", subtype="冲突进展",
                              actor="乌方", region="俄乌", summary="推进",
                              verification_status="draft", article_id=art.id,
                              merge_key="e2")
        weapons.upsert_weapon(db, name="验证机", origin="美国", weapon_type="战斗机",
                              params_text="参数待核", lifecycle_status="研发",
                              merge_key="w1", verification_status="draft",
                              article_id=art.id)
        indicators.upsert_indicator(db, indicator="CPI", region="中国", period="2026-08",
                                    value=0.4, unit="%", merge_key="i1", article_id=art.id)
        stances.create_stance(db, topic="对华", actor="美国商务部", stance_text="扩大",
                              tone="趋严", stated_at=now,
                              verification_status="confirmed", article_id=art.id)
        snapshots.insert_snapshots(db, [
            dict(asset_code="^spx", asset_name="标普500", asset_class="index",
                 price=5980.0, batch_id="b1", source="stooq"),
        ])


def test_board_endpoints(client):
    _seed(client)
    tl = client.get("/api/categories/politics/timeline").json()
    assert len(tl["items"]) == 1 and tl["items"][0]["verification_status"] == "confirmed"
    st = client.get("/api/politics/stances?topic=对华").json()
    assert st["items"][0]["tone"] == "趋严"
    wp = client.get("/api/military/weapons").json()
    assert wp["items"] == []  # 草稿武器不进入板块展示
    ind = client.get("/api/economy/indicators?indicator=CPI").json()
    assert ind["items"][0]["value"] == 0.4
    sn = client.get("/api/finance/snapshots?batch_id=b1").json()
    assert sn["items"][0]["price"] == 5980.0


def test_moderation_flow(client):
    _seed(client)
    queue = client.get("/api/moderations").json()["items"]
    weapon_item = next(item for item in queue if item["type"] == "weapon")
    assert weapon_item["params_text"] == "参数待核"

    resp = client.patch(f"/api/moderations/weapon/{weapon_item['id']}",
                        json={"action": "confirm"})
    assert resp.status_code == 200 and resp.json()["verification_status"] == "confirmed"
    assert client.get("/api/military/weapons").json()["items"][0]["name"] == "验证机"

    timeline_item = next(item for item in queue if item["type"] == "timeline")
    edited = client.patch(f"/api/moderations/timeline/{timeline_item['id']}",
                          json={"action": "edit", "summary": "已修改的进展",
                                "importance": "high"})
    assert edited.status_code == 200 and edited.json()["summary"] == "已修改的进展"

    remaining = client.get("/api/moderations").json()["items"]
    assert all(item["type"] != "weapon" for item in remaining)
