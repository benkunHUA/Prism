from datetime import datetime

from app.repositories import indicators, snapshots, stances, timeline, weapons
from app.services.reports.context import build_board_context
from app.services.reports.specs import spec_for


def _seed_structured(db):
    timeline.upsert_event(
        db, category="military", subtype="冲突进展", actor="双方", region="俄乌",
        occurred_at=datetime(2026, 10, 11, 9, 0), summary="东部战线推进 3 公里",
        importance="high", verification_status="confirmed", merge_key="ev1",
    )
    timeline.upsert_event(
        db, category="military", subtype="冲突进展", actor="双方", region="俄乌",
        summary="未经证实的草稿事件", verification_status="draft", merge_key="ev2",
    )
    weapons.upsert_weapon(db, name="PrSM", origin="美国", weapon_type="导弹",
                          lifecycle_status="测试", params_text="射程 499 公里",
                          verification_status="confirmed", merge_key="w1")
    indicators.upsert_indicator(db, indicator="CPI", region="中国", period="2026-09",
                                value=0.4, unit="%", previous=0.5, forecast=0.3,
                                merge_key="i1")
    snapshots.insert_snapshots(db, [
        dict(asset_code="100.SPX", asset_name="标普500", asset_class="index",
             price=5800.0, change_pct=1.2, captured_at=datetime(2026, 10, 11, 21, 0),
             batch_id="b1", source="eastmoney"),
        dict(asset_code="100.NDX", asset_name="纳斯达克", asset_class="index",
             price=20300.0, change_pct=-0.4, captured_at=datetime(2026, 10, 11, 21, 0),
             batch_id="b1", source="eastmoney"),
        dict(asset_code="100.SPX", asset_name="标普500", asset_class="index",
             price=5730.0, change_pct=0.3, captured_at=datetime(2026, 10, 10, 21, 0),
             batch_id="b0", source="eastmoney"),
    ])
    stances.create_stance(db, topic="俄乌", actor="美国国务院", stance_text="继续援乌",
                          tone="支持", stated_at=datetime(2026, 10, 11, 10, 0),
                          verification_status="confirmed")


def test_military_context_contains_weapons_and_confirmed_events_only(db):
    _seed_structured(db)
    text = build_board_context(db, spec_for("military"))
    assert "### 武器档案" in text and "PrSM" in text
    assert "参数: 射程 499 公里" in text
    assert "东部战线推进 3 公里" in text
    assert "未经证实的草稿事件" not in text


def test_economy_context_contains_indicator_numbers(db):
    _seed_structured(db)
    text = build_board_context(db, spec_for("economy"))
    assert "CPI" in text and "0.4" in text and "前值 0.5" in text and "预期 0.3" in text


def test_finance_context_compares_with_previous_batch(db):
    _seed_structured(db)
    text = build_board_context(db, spec_for("finance"))
    assert "标普500" in text and "+1.20%" in text and "上轮涨跌 +0.30%" in text
    assert "纳斯达克" in text and "-0.40%" in text


def test_politics_context_carries_stances(db):
    _seed_structured(db)
    text = build_board_context(db, spec_for("politics"))
    assert "### 议题立场" in text and "美国国务院" in text and "继续援乌" in text
    assert "东部战线推进 3 公里" not in text


def test_empty_database_returns_empty_string(db):
    assert build_board_context(db, spec_for("military")) == ""
