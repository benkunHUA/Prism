# backend/app/core/geo.py
"""地区词表与归一化。只放数据与纯函数，不依赖 ORM 与配置。"""

from __future__ import annotations

import re

# code 用 ISO 3166-1 alpha-2 小写；lng/lat 为预置质心，不从几何现算
COUNTRIES: list[dict] = [
    {"code": "us", "name_zh": "美国", "lng": -98.5, "lat": 39.8,
     "aliases": ["美国", "美方", "华盛顿", "白宫", "United States", "America", "USA", "US"]},
    {"code": "ca", "name_zh": "加拿大", "lng": -106.3, "lat": 56.1,
     "aliases": ["加拿大", "渥太华", "Canada"]},
    {"code": "mx", "name_zh": "墨西哥", "lng": -102.6, "lat": 23.6,
     "aliases": ["墨西哥", "Mexico", "Mexican"]},
    {"code": "br", "name_zh": "巴西", "lng": -51.9, "lat": -14.2,
     "aliases": ["巴西", "Brazil", "Brazilian"]},
    {"code": "ar", "name_zh": "阿根廷", "lng": -63.6, "lat": -38.4,
     "aliases": ["阿根廷", "Argentina"]},
    {"code": "gb", "name_zh": "英国", "lng": -3.4, "lat": 55.4,
     "aliases": ["英国", "伦敦", "Britain", "United Kingdom", "UK"]},
    {"code": "fr", "name_zh": "法国", "lng": 2.2, "lat": 46.6,
     "aliases": ["法国", "巴黎", "France", "French"]},
    {"code": "de", "name_zh": "德国", "lng": 10.4, "lat": 51.2,
     "aliases": ["德国", "柏林", "Germany", "German"]},
    {"code": "it", "name_zh": "意大利", "lng": 12.6, "lat": 41.9,
     "aliases": ["意大利", "Italy", "Italian"]},
    {"code": "es", "name_zh": "西班牙", "lng": -3.7, "lat": 40.5,
     "aliases": ["西班牙", "Spain", "Spanish"]},
    {"code": "pl", "name_zh": "波兰", "lng": 19.1, "lat": 52.1,
     "aliases": ["波兰", "Poland", "Polish"]},
    {"code": "se", "name_zh": "瑞典", "lng": 18.6, "lat": 60.1,
     "aliases": ["瑞典", "Sweden", "Swedish"]},
    {"code": "ru", "name_zh": "俄罗斯", "lng": 105.3, "lat": 61.5,
     "aliases": ["俄罗斯", "俄方", "俄军", "莫斯科", "Russia", "Russian"]},
    {"code": "ua", "name_zh": "乌克兰", "lng": 31.2, "lat": 48.4,
     "aliases": ["乌克兰", "基辅", "Ukraine", "Ukrainian"]},
    {"code": "tr", "name_zh": "土耳其", "lng": 35.2, "lat": 39.0,
     "aliases": ["土耳其", "Turkey", "Turkish"]},
    {"code": "il", "name_zh": "以色列", "lng": 34.9, "lat": 31.0,
     "aliases": ["以色列", "特拉维夫", "Israel", "Israeli"]},
    {"code": "ir", "name_zh": "伊朗", "lng": 53.7, "lat": 32.4,
     "aliases": ["伊朗", "德黑兰", "Iran", "Iranian"]},
    {"code": "iq", "name_zh": "伊拉克", "lng": 43.7, "lat": 33.2,
     "aliases": ["伊拉克", "Iraq"]},
    {"code": "sa", "name_zh": "沙特阿拉伯", "lng": 45.1, "lat": 23.9,
     "aliases": ["沙特阿拉伯", "沙特", "Saudi Arabia", "Saudi"]},
    {"code": "ae", "name_zh": "阿联酋", "lng": 53.8, "lat": 23.4,
     "aliases": ["阿联酋", "迪拜", "United Arab Emirates", "UAE"]},
    {"code": "qa", "name_zh": "卡塔尔", "lng": 51.2, "lat": 25.4,
     "aliases": ["卡塔尔", "Qatar"]},
    {"code": "sy", "name_zh": "叙利亚", "lng": 38.5, "lat": 35.0,
     "aliases": ["叙利亚", "大马士革", "Syria", "Syrian"]},
    {"code": "ye", "name_zh": "也门", "lng": 48.5, "lat": 15.6,
     "aliases": ["也门", "Yemen"]},
    {"code": "lb", "name_zh": "黎巴嫩", "lng": 35.9, "lat": 33.9,
     "aliases": ["黎巴嫩", "贝鲁特", "Lebanon"]},
    {"code": "eg", "name_zh": "埃及", "lng": 30.8, "lat": 26.8,
     "aliases": ["埃及", "开罗", "Egypt"]},
    {"code": "za", "name_zh": "南非", "lng": 22.9, "lat": -30.6,
     "aliases": ["南非", "South Africa"]},
    {"code": "ng", "name_zh": "尼日利亚", "lng": 8.7, "lat": 9.1,
     "aliases": ["尼日利亚", "Nigeria"]},
    {"code": "ke", "name_zh": "肯尼亚", "lng": 37.9, "lat": 0.0,
     "aliases": ["肯尼亚", "内罗毕", "Kenya"]},
    {"code": "cg", "name_zh": "刚果共和国", "lng": 15.8, "lat": -0.8,
     "aliases": ["刚果", "刚果布", "Republic of the Congo"]},
    {"code": "cd", "name_zh": "刚果民主共和国", "lng": 21.8, "lat": -4.0,
     "aliases": ["刚果民主共和国", "刚果金", "DR Congo", "DRC"]},
    {"code": "in", "name_zh": "印度", "lng": 78.7, "lat": 20.6,
     "aliases": ["印度", "新德里", "India", "Indian"]},
    {"code": "pk", "name_zh": "巴基斯坦", "lng": 69.3, "lat": 30.4,
     "aliases": ["巴基斯坦", "Pakistan"]},
    {"code": "cn", "name_zh": "中国", "lng": 104.2, "lat": 35.9,
     "aliases": ["中国", "中方", "北京", "China", "Chinese"]},
    {"code": "jp", "name_zh": "日本", "lng": 138.0, "lat": 36.2,
     "aliases": ["日本", "东京", "Japan", "Japanese"]},
    {"code": "kr", "name_zh": "韩国", "lng": 127.8, "lat": 35.9,
     "aliases": ["韩国", "首尔", "South Korea", "Korea", "Korean"]},
    {"code": "kp", "name_zh": "朝鲜", "lng": 127.5, "lat": 40.3,
     "aliases": ["朝鲜", "平壤", "North Korea", "DPRK"]},
    {"code": "sg", "name_zh": "新加坡", "lng": 103.8, "lat": 1.35,
     "aliases": ["新加坡", "Singapore"]},
    {"code": "id", "name_zh": "印度尼西亚", "lng": 113.9, "lat": -0.8,
     "aliases": ["印度尼西亚", "印尼", "雅加达", "Indonesia"]},
    {"code": "vn", "name_zh": "越南", "lng": 108.3, "lat": 14.1,
     "aliases": ["越南", "Vietnam"]},
    {"code": "ph", "name_zh": "菲律宾", "lng": 121.8, "lat": 12.9,
     "aliases": ["菲律宾", "Philippines"]},
    {"code": "th", "name_zh": "泰国", "lng": 100.9, "lat": 15.9,
     "aliases": ["泰国", "曼谷", "Thailand"]},
    {"code": "au", "name_zh": "澳大利亚", "lng": 133.8, "lat": -25.3,
     "aliases": ["澳大利亚", "澳洲", "Australia"]},
]

# 热点区是一等地区，绝不并入所属国家（见 spec §3）
HOTSPOTS: list[dict] = [
    {"code": "tw_strait", "name_zh": "台海", "lng": 119.5, "lat": 24.0,
     "aliases": ["台海", "台湾海峡", "Taiwan Strait"]},
    {"code": "gaza", "name_zh": "加沙", "lng": 34.4, "lat": 31.4,
     "aliases": ["加沙", "加沙地带", "Gaza"]},
    {"code": "south_china_sea", "name_zh": "南海", "lng": 114.0, "lat": 12.0,
     "aliases": ["南海", "南中国海", "South China Sea"]},
    {"code": "red_sea", "name_zh": "红海", "lng": 38.5, "lat": 18.0,
     "aliases": ["红海", "曼德海峡", "Red Sea"]},
    {"code": "arctic", "name_zh": "北极", "lng": 0.0, "lat": 78.0,
     "aliases": ["北极", "北极航道", "Arctic"]},
]

REGIONS: list[dict] = COUNTRIES + HOTSPOTS
REGION_MAP: dict[str, dict] = {r["code"]: r for r in REGIONS}
REGION_NAMES: dict[str, str] = {r["code"]: r["name_zh"] for r in REGIONS}


def _build_alias_tables() -> tuple[dict[str, str], list[tuple[re.Pattern[str], str]]]:
    exact: dict[str, str] = {}
    for region in REGIONS:
        # code 自身可回环：normalize_region("south_china_sea") == "south_china_sea"，
        # 否则 "China" 会从 code 里的 _china_ 命中 cn；code 先于别名登记，保证优先。
        exact[region["code"]] = region["code"]
        for alias in region["aliases"]:
            key = alias.strip().lower()
            if key and key not in exact:
                exact[key] = region["code"]
    # 子串匹配只用于长度 >= 3 的别名，长别名优先，避免 "US" 命中 "Russia"
    substrings = sorted(
        ((a.strip().lower(), r["code"]) for r in REGIONS for a in r["aliases"]
         if len(a.strip()) >= 3),
        key=lambda pair: -len(pair[0]),
    )
    # 一份正则覆盖全部别名：CJK 别名不含 [a-z0-9]，词边界行为与裸子串包含一致
    patterns = [
        (re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"), code)
        for alias, code in substrings
    ]
    return exact, patterns


_EXACT, _ALIAS_SUB = _build_alias_tables()


def normalize_region(text: str | None) -> str | None:
    """把自由文本地区名归一化成词表 code；无法归一返回 None（调用方直接丢弃）。"""
    if not text:
        return None
    key = text.strip().lower()
    if not key:
        return None
    hit = _EXACT.get(key)
    if hit:
        return hit
    for pattern, code in _ALIAS_SUB:
        if pattern.search(key):
            return code
    return None
