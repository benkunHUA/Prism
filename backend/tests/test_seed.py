from app.core.config import Settings
from app.core.geo import REGION_MAP
from app.models.entities import Source
from app.repositories.sources import create_source
from app.services.seed import add_missing_seed_sources, load_seed_sources, seed_defaults


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


def test_seed_covers_china_and_asia(db):
    regions = {item["region"] for item in load_seed_sources()}
    assert {"cn", "jp", "kr", "vn", "id", "ph", "th"} <= regions


def test_seed_covers_ukraine_and_middle_east_conflicts():
    seeds = load_seed_sources()
    military = [item for item in seeds if "military" in item["categories"]]
    urls = {item["url"] for item in military}

    assert "https://www.ukrinform.net/rss/block-lastnews" in urls
    assert "https://www.france24.com/en/middle-east/rss" in urls
    assert "https://news.un.org/feed/subscribe/en/news/region/middle-east/feed/rss.xml" in urls


def test_seed_covers_international_oil_sources():
    seeds = load_seed_sources()
    urls = {item["url"] for item in seeds if "finance" in item["categories"]}

    assert "https://www.eia.gov/rss/todayinenergy.xml" in urls
    assert "https://oilprice.com/rss/main" in urls
    assert "https://www.investing.com/rss/news_11.rss" in urls


def test_add_missing_seed_sources_only_adds_new(db):
    seeds = load_seed_sources()
    kept = seeds[0]
    create_source(db, name="已有源", url=kept["url"], feed_type="rss",
                  lang="en", region=kept["region"], categories=["politics"])

    added = add_missing_seed_sources(db)

    assert len(added) == len(seeds) - 1
    assert kept["name"] not in added
    urls = [url for (url,) in db.query(Source.url).all()]
    assert len(urls) == len(set(urls)) == len(seeds)
    assert add_missing_seed_sources(db) == []          # 再跑一次无新增
