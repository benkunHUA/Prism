# backend/tests/test_geo.py
from app.core.geo import COUNTRIES, HOTSPOTS, REGION_MAP, REGION_NAMES, normalize_region


def test_normalize_hits_chinese_and_english_aliases():
    assert normalize_region("美国") == "us"
    assert normalize_region("United States") == "us"
    assert normalize_region(" 美方 ") == "us"


def test_normalize_keeps_hotspot_separate_from_country():
    assert normalize_region("台海") == "tw_strait"
    assert normalize_region("加沙地带") == "gaza"
    assert normalize_region("加沙") != "il"


def test_normalize_returns_none_for_unknown_and_empty():
    assert normalize_region("火星") is None
    assert normalize_region("") is None
    assert normalize_region(None) is None


def test_substring_pass_requires_length_and_word_boundary():
    # "US" 不能命中 Russia；"Korea" 不能抢走 North Korea
    assert normalize_region("Russia") == "ru"
    assert normalize_region("North Korea") == "kp"
    assert normalize_region("South Korea") == "kr"
    assert normalize_region("刚果民主共和国") == "cd"
    assert normalize_region("刚果") == "cg"


def test_region_table_is_internally_consistent():
    regions = COUNTRIES + HOTSPOTS
    codes = [r["code"] for r in regions]
    assert len(codes) == len(set(codes))
    assert set(REGION_NAMES) == set(codes)
    assert set(REGION_MAP) == set(codes)
    aliases = [a.strip().lower() for r in regions for a in r["aliases"]]
    assert len(aliases) == len(set(aliases)), "别名重复会让匹配结果依赖插入顺序"
    for region in regions:
        assert -180 <= region["lng"] <= 180
        assert -90 <= region["lat"] <= 90
        assert region["aliases"]
