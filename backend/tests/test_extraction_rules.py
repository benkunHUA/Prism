from app.services.extraction.prompts import build_extraction_prompt
from app.services.extraction.risk import event_auto_verification
from app.services.extraction.schemas import MilitaryExtraction, PoliticsExtraction


def test_schemas_accept_example_json():
    data = {
        "events": [
            {"subtype": "外交与峰会", "actor": "美日韩", "region": "亚太",
             "occurred_at": "2026-09-08T10:00:00", "summary": "举行三方会晤",
             "importance": "high"},
        ],
        "stances": [
            {"topic": "对华", "actor": "美国商务部", "stance_text": "名单扩大",
             "tone": "趋严", "stated_at": "2026-09-08T08:00:00"},
        ],
    }
    parsed = PoliticsExtraction.model_validate(data)
    assert parsed.events[0].summary == "举行三方会晤"
    assert parsed.stances[0].tone == "趋严"


def test_military_schema_has_weapons():
    data = {
        "weapons": [
            {"name": "第六代验证机", "origin": "美国", "weapon_type": "战斗机",
             "params_text": "飞翼布局", "lifecycle_status": "研发"},
        ],
        "conflicts": [],
    }
    parsed = MilitaryExtraction.model_validate(data)
    assert parsed.weapons[0].lifecycle_status == "研发"


def test_prompt_mentions_category_and_json():
    prompt = build_extraction_prompt("politics", title="会晤", body="正文", url="https://x.test/a")
    assert "politics" in prompt and "JSON" in prompt


def test_auto_verification_rules():
    assert event_auto_verification("economy", "货币政策", "美联储决定维持利率不变") == "confirmed"
    assert event_auto_verification("military", "冲突进展", "乌方称击退进攻") == "draft"
    assert event_auto_verification("politics", "外交与峰会", "峰会召开") == "draft"
    assert event_auto_verification("finance", "融资/IPO/并购", "宣布收购案") == "confirmed"
