import json
from pathlib import Path

from app.core.geo import COUNTRIES

ASSET = Path(__file__).resolve().parents[2] / "frontend" / "src" / "assets" / "world.geo.json"

# 110m 底图不含几何的微型国家：地图上无法按区域点选，属已知豁免
SMALL_STATES_WITHOUT_GEOMETRY = {"sg"}


def test_asset_covers_every_country():
    payload = json.loads(ASSET.read_text(encoding="utf-8"))
    codes = {feature["properties"]["name"] for feature in payload["features"]}
    missing = [
        country["code"]
        for country in COUNTRIES
        if country["code"] not in codes and country["code"] not in SMALL_STATES_WITHOUT_GEOMETRY
    ]
    assert missing == [], f"这些国家在底图里没有几何，地图上会点不出来：{missing}"
