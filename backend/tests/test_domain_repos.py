from app.models.entities import Category
from app.repositories import indicators, snapshots, sources, stances, timeline, weapons


def _article(db):
    src = sources.create_source(db, name="S", url="https://example.com/rss",
                                feed_type="rss", lang="en", categories=[Category.politics.value])
    from app.repositories import articles

    articles.insert_articles(db, [dict(source_id=src.id, category="politics",
                                       url="https://example.com/a", title="A", summary="s",
                                       content_text="", published_at=None, lang="en",
                                       dedupe_hash="ha")])
    return articles.list_articles(db, category="politics")[0]


def test_timeline_upsert_and_list(db):
    row, created = timeline.upsert_event(
        db, category="politics", subtype="立法与投票", actor="欧盟议会",
        region="欧盟", summary="修正案通过", importance="medium",
        verification_status="confirmed", article_id=None, group_key=None,
        merge_key="mk1",
    )
    assert created is True and row.verification_status == "confirmed"
    row2, created2 = timeline.upsert_event(
        db, category="politics", subtype="立法与投票", actor="欧盟议会",
        region="欧盟", summary="修正案二读通过", importance="high",
        verification_status="confirmed", article_id=None, group_key=None,
        merge_key="mk1",
    )
    assert created2 is False and row2.id == row.id
    assert row2.summary == "修正案二读通过"
    assert len(timeline.list_events(db, category="politics")) == 1


def test_weapon_upsert_updates_not_duplicates(db):
    w1, c1 = weapons.upsert_weapon(db, name="X", original_name="", origin="US",
                                   weapon_type="导弹", params_text="v1",
                                   lifecycle_status="研发", merge_key="w1",
                                   verification_status="draft", article_id=None)
    assert c1 is True
    w2, c2 = weapons.upsert_weapon(db, name="X", original_name="", origin="US",
                                   weapon_type="导弹", params_text="v2 新增射程",
                                   lifecycle_status="测试", merge_key="w1",
                                   verification_status="draft", article_id=None)
    assert c2 is False and w2.id == w1.id
    assert w2.params_text == "v2 新增射程" and w2.lifecycle_status == "测试"
    assert len(weapons.list_weapons(db)) == 1


def test_indicator_correction_overwrites(db):
    i1, c1 = indicators.upsert_indicator(db, indicator="CPI", region="中国",
                                         period="2026-08", value=0.4, unit="%",
                                         previous=0.5, forecast=0.6, merge_key="i1",
                                         article_id=None)
    assert c1 is True
    indicators.upsert_indicator(db, indicator="CPI", region="中国", period="2026-08",
                                value=0.3, unit="%", previous=0.5, forecast=0.6,
                                merge_key="i1", article_id=None)
    assert indicators.list_indicators(db, indicator="CPI", region="中国")[0].value == 0.3


def test_stance_appends_history(db):
    stances.create_stance(db, topic="对华", actor="美国商务部", stance_text="名单扩大",
                          tone="趋严", verification_status="draft", article_id=None)
    stances.create_stance(db, topic="对华", actor="美国商务部", stance_text="进一步扩大",
                          tone="趋严", verification_status="confirmed", article_id=None)
    rows = stances.list_stances(db, topic="对华", actor="美国商务部")
    assert len(rows) == 2
    assert rows[0].stance_text == "进一步扩大"


def test_snapshot_batch(db):
    snapshots.insert_snapshots(db, [
        dict(asset_code="^spx", asset_name="标普500", asset_class="index",
             price=5980.0, change_pct=-0.8, batch_id="b1", source="stooq"),
        dict(asset_code="xau", asset_name="黄金", asset_class="commodity",
             price=2610.0, change_pct=0.6, batch_id="b1", source="stooq"),
    ])
    snapshots.insert_snapshots(db, [
        dict(asset_code="^spx", asset_name="标普500", asset_class="index",
             price=5990.0, change_pct=0.2, batch_id="b2", source="stooq"),
    ])
    assert snapshots.latest_batch_id(db) == "b2"
    assert len(snapshots.list_snapshots(db, batch_id="b1")) == 2
    assert len(snapshots.list_snapshots(db)) == 3
