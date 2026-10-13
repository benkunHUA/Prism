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


def test_region_codes_round_trip_and_hotspots_never_resolve_to_country():
    assert normalize_region("south_china_sea") == "south_china_sea"
    assert normalize_region("tw_strait") == "tw_strait"
    country_codes = {country["code"] for country in COUNTRIES}
    for region in COUNTRIES + HOTSPOTS:
        assert normalize_region(region["code"]) == region["code"]
    for hotspot in HOTSPOTS:
        assert normalize_region(hotspot["code"]) not in country_codes


def test_single_alias_pattern_list_covers_every_long_alias():
    from app.core.geo import _ALIAS_SUB

    long_aliases = [
        (alias.strip().lower(), region["code"])
        for region in COUNTRIES + HOTSPOTS
        for alias in region["aliases"]
        if len(alias.strip()) >= 3
    ]
    assert len(_ALIAS_SUB) == len(long_aliases), "去掉 isascii 分流后正则列表必须覆盖全部别名"
    for alias, code in long_aliases:
        assert any(hit == code and pattern.search(alias) for pattern, hit in _ALIAS_SUB), alias
    # 非 ASCII 拉丁文本同走这条正则：拼写不在词表内则不命中，词边界依旧生效
    assert normalize_region("México") is None
    assert normalize_region("mexicanos") is None
