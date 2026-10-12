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


def _iter_positions(coordinates):
    if coordinates and isinstance(coordinates[0], (int, float)):
        yield coordinates
        return
    for child in coordinates or []:
        yield from _iter_positions(child)


def test_asset_geometry_is_usable():
    payload = json.loads(ASSET.read_text(encoding="utf-8"))
    assert payload["features"], "底图资产不能为空"
    for feature in payload["features"]:
        name = feature["properties"]["name"]
        geometry = feature["geometry"]
        assert geometry["type"] in {"Polygon", "MultiPolygon"}, f"{name} 几何类型异常"
        positions = list(_iter_positions(geometry["coordinates"]))
        assert positions, f"{name} 没有坐标"
        for lng, lat in positions:
            assert -180 <= lng <= 180 and -90 <= lat <= 90, f"{name} 坐标越界：{lng},{lat}"
