from app.core.config import Settings
from app.core.geo import REGION_MAP
from app.models.entities import Source
from app.services.seed import seed_defaults


def test_seed_defaults_sets_valid_source_regions(db):
    assert seed_defaults(db, Settings(_env_file=None)) is True

    by_name = {s.name: s.region for s in db.query(Source).all()}
    assert by_name
    assert all(by_name.values()), "内置源都应带来源地区兜底"
    assert set(by_name.values()) <= set(REGION_MAP)
    assert by_name["美联储新闻发布"] == "us"
    assert by_name["BBC 世界新闻"] == "gb"


def test_seed_defaults_skips_when_sources_exist(db):
    seed_defaults(db, Settings(_env_file=None))
    assert seed_defaults(db, Settings(_env_file=None)) is False
