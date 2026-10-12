# Aurora 世界地图看板 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `/` 看板从统计卡片页改成「世界地图 + 右侧地区面板」：底层国家填色看热度、上层彩点看板块构成，点地区就地看该地区新闻。

**Architecture:** 后端在既有抽取管线里顺带产出文章级地区标签（零额外 LLM 调用）落到新表 `article_regions`，再由一个只读聚合接口把「地区 × 板块」计数交给前端；前端用 ECharts 的 `geo` + `map` + `scatter` 双层渲染，右栏面板在「地区榜 / 地区新闻」两态间切换。

**Tech Stack:** FastAPI + SQLAlchemy 2 + pytest（后端）；React 18 + Vite + TS + Ant Design 5 + ECharts 5 + vitest（前端）；底图用随仓库提交的 Natural Earth 简化 GeoJSON，不依赖在线瓦片。

**Spec:** `docs/superpowers/specs/2026-10-12-aurora-world-map-dashboard-design.md`

**每个任务结束都要跑：** 后端 `cd backend && uv run pytest -q`；前端 `cd frontend && npm test && npm run typecheck`。

---

## 文件结构

**后端新增**

| 文件 | 职责 |
| --- | --- |
| `backend/app/core/geo.py` | 地区词表（国家 + 热点区）与 `normalize_region()` 归一化，纯数据 + 纯函数 |
| `backend/app/repositories/article_regions.py` | 文章↔地区关联的写入、去重、聚合查询 |
| `backend/app/services/geo_tag.py` | 源地区兜底策略（不碰 HTTP，只做业务规则） |
| `backend/app/api/routes_geo.py` | 聚合接口 + 地区文章接口，只做参数校验与转发 |
| `backend/tests/test_geo.py`、`test_article_regions.py`、`test_api_geo.py` | 对应单测 |

**后端修改**

| 文件 | 改动 |
| --- | --- |
| `backend/app/models/entities.py` | 新增 `ArticleRegion` 表；`Source` 加 `region` 列 |
| `backend/app/services/extraction/schemas.py` | 四个板块模型各加 `regions: list[str]` |
| `backend/app/services/extraction/prompts.py` | 提示词增加地区字段说明 |
| `backend/app/services/extraction/extractor.py` | 抽取结果写 `article_regions` |
| `backend/app/services/flow.py` | 采集分支接兜底补标 |
| `backend/app/repositories/sources.py`、`backend/app/api/routes_sources.py` | 源地区字段 |
| `backend/app/main.py` | 注册 `routes_geo` |

**前端新增**

| 文件 | 职责 |
| --- | --- |
| `frontend/src/constants/geo.ts` | 时间窗选项、热力配色、文案等常量 |
| `frontend/src/utils/geo.ts` | 纯函数：类别计数重算、按地区逐板块展开散点、分位数配色 |
| `frontend/src/utils/geo.test.ts` | 上面纯函数的单测 |
| `frontend/src/components/map/WorldMap.tsx` | ECharts 实例封装（双层 option、点击、resize） |
| `frontend/src/components/map/RegionPanel.tsx` | 右栏两态（地区榜 ↔ 地区新闻列表） |
| `frontend/src/components/map/MapLegend.tsx` | 板块图例筛选 + 时间窗切换 + 未定位计数 |
| `frontend/src/components/map/CategoryStrip.tsx` | 四板块 chip 条（承接原仪表盘板块卡信息） |
| `frontend/src/pages/MapBoardPage.tsx` | 页面组合与数据拉取 |
| `frontend/src/assets/world.geo.json` | 简化世界边界（构建产物，提交进仓库） |
| `frontend/scripts/build-world-geo.mjs` | 从 Natural Earth 原始 GeoJSON 生成上面的资产 |

**前端修改**

| 文件 | 改动 |
| --- | --- |
| `frontend/src/api/types.ts`、`endpoints.ts` | 新增 geojson 类型与两个端点 |
| `frontend/src/App.tsx` | `/` 指向 `MapBoardPage` |
| `frontend/src/pages/DashboardPage.tsx` | 删除（信息由 `CategoryStrip` + `StatCards` 承接） |
| `frontend/src/pages/SourcesPage.tsx` | 源地区下拉 |

---

## Task 1: 地区词表与归一化

**Files:**
- Create: `backend/app/core/geo.py`
- Test: `backend/tests/test_geo.py`

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_geo.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.core.geo'`

- [ ] **Step 3: 实现词表**

```python
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


def _build_alias_tables() -> tuple[dict[str, str], list[tuple[str, str]], list[tuple[re.Pattern[str], str]]]:
    exact: dict[str, str] = {}
    for region in REGIONS:
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
    cjk = [(alias, code) for alias, code in substrings if not alias.isascii()]
    latin = [
        (re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"), code)
        for alias, code in substrings if alias.isascii()
    ]
    return exact, cjk, latin


_EXACT, _CJK_SUB, _LATIN_SUB = _build_alias_tables()


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
    for alias, code in _CJK_SUB:
        if alias in key:
            return code
    for pattern, code in _LATIN_SUB:
        if pattern.search(key):
            return code
    return None
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_geo.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/geo.py backend/tests/test_geo.py
git commit -m "feat(backend): 地区词表与归一化"
```

---

## Task 2: 数据模型（`article_regions` + `Source.region`）

**Files:**
- Modify: `backend/app/models/entities.py`
- Test: `backend/tests/test_models.py`（在文件末尾追加）

- [ ] **Step 1: 写失败测试**

```python
# 追加到 backend/tests/test_models.py 末尾
def test_article_region_unique_and_cascade(db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.models.entities import Article, ArticleRegion

    article = Article(category="politics", url="https://example.com/ar", title="T",
                      summary="", content_text="", lang="en", dedupe_hash="har")
    db.add(article)
    db.commit()
    db.add(ArticleRegion(article_id=article.id, region_code="us"))
    db.commit()

    db.add(ArticleRegion(article_id=article.id, region_code="us"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.delete(article)
    db.commit()
    assert db.query(ArticleRegion).count() == 0  # 文章删除时级联清掉标签


def test_source_region_defaults_to_empty(db):
    from app.models.entities import Source

    db.add(Source(name="S", url="https://example.com/sr"))
    db.commit()
    assert db.query(Source).first().region == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_models.py -q`
Expected: FAIL —— `ImportError: cannot import name 'ArticleRegion'`

- [ ] **Step 3: 加模型与列**

在 `backend/app/models/entities.py` 的 `Article` 类之后插入新表：

```python
class ArticleRegion(Base):
    """文章级地区标签：llm=抽取打标，source=来源兜底。"""

    __tablename__ = "article_regions"
    __table_args__ = (UniqueConstraint("article_id", "region_code", name="uq_article_region"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    region_code: Mapped[str] = mapped_column(String(32), index=True)
    source: Mapped[str] = mapped_column(String(10), default="llm")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


```

并在 `Source` 类里、`lang` 之后加一列：

```python
    region: Mapped[str] = mapped_column(String(32), default="")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_models.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/entities.py backend/tests/test_models.py
git commit -m "feat(backend): 新增 article_regions 表与来源地区列"
```

---

## Task 3: 地区标签仓储

**Files:**
- Create: `backend/app/repositories/article_regions.py`
- Test: `backend/tests/test_article_regions.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_article_regions.py
from datetime import datetime, timedelta, timezone

from app.repositories import article_regions as regions_repo
from app.repositories import articles as articles_repo
from app.repositories import sources as sources_repo


def _seed_article(db, *, category: str, url: str, dedupe: str, hours_ago: int = 0):
    source = sources_repo.create_source(
        db, name=f"S-{dedupe}", url=f"https://example.com/{dedupe}",
        feed_type="rss", lang="en", categories=[category],
    )
    when = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours_ago)
    articles_repo.insert_articles(db, [
        dict(source_id=source.id, category=category, url=url, title=f"T-{dedupe}",
             summary="s", content_text="", published_at=when, lang="en", dedupe_hash=dedupe),
    ])
    article = next(a for a in articles_repo.list_articles(db) if a.dedupe_hash == dedupe)
    article.fetched_at = when
    db.commit()
    return article


def test_write_regions_dedupes_and_skips_existing(db):
    article = _seed_article(db, category="politics", url="https://example.com/a1", dedupe="a1")
    assert regions_repo.write_regions(db, article_id=article.id,
                                      codes=["us", "gaza", "us", ""]) == 2
    assert regions_repo.codes_for_article(db, article.id) == {"us", "gaza"}
    assert regions_repo.write_regions(db, article_id=article.id, codes=["us"]) == 0


def test_count_by_region_and_untagged_respect_window(db):
    fresh = _seed_article(db, category="military", url="https://example.com/a2", dedupe="a2")
    stale = _seed_article(db, category="military", url="https://example.com/a3",
                          dedupe="a3", hours_ago=48)
    regions_repo.write_regions(db, article_id=fresh.id, codes=["il", "gaza"])
    regions_repo.write_regions(db, article_id=stale.id, codes=["ua"])

    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    rows = {(code, cat): count for code, cat, count in regions_repo.count_by_region(db, since)}
    assert rows[("il", "military")] == 1
    assert rows[("gaza", "military")] == 1
    assert ("ua", "military") not in rows  # 48 小时前的文章被窗口排除
    assert regions_repo.untagged_count(db, since) == 0

    _seed_article(db, category="military", url="https://example.com/a4", dedupe="a4")
    assert regions_repo.untagged_count(db, since) == 1
    assert regions_repo.article_ids_with_regions(db, [fresh.id, stale.id]) == {fresh.id, stale.id}


def test_list_articles_by_region_filters_category(db):
    first = _seed_article(db, category="politics", url="https://example.com/b1", dedupe="b1")
    second = _seed_article(db, category="finance", url="https://example.com/b2", dedupe="b2")
    regions_repo.write_regions(db, article_id=first.id, codes=["us"])
    regions_repo.write_regions(db, article_id=second.id, codes=["us"])
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)

    all_items = regions_repo.list_articles_by_region(db, code="us", since=since)
    assert {a.id for a in all_items} == {first.id, second.id}
    finance_only = regions_repo.list_articles_by_region(db, code="us", since=since,
                                                       category="finance")
    assert [a.id for a in finance_only] == [second.id]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_article_regions.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.repositories.article_regions'`

- [ ] **Step 3: 实现仓储**

```python
# backend/app/repositories/article_regions.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import Article, ArticleRegion


def write_regions(db: Session, *, article_id: int, codes: list[str],
                  source: str = "llm") -> int:
    """写入文章地区标签：按 code 去重、跳过已存在的，返回新增条数。"""
    unique = [code for code in dict.fromkeys(codes) if code]
    if not unique:
        return 0
    existing = {
        row[0]
        for row in db.query(ArticleRegion.region_code)
        .filter(ArticleRegion.article_id == article_id,
                ArticleRegion.region_code.in_(unique))
        .all()
    }
    created = 0
    for code in unique:
        if code in existing:
            continue
        db.add(ArticleRegion(article_id=article_id, region_code=code, source=source))
        created += 1
    db.commit()
    return created


def codes_for_article(db: Session, article_id: int) -> set[str]:
    return {
        row[0]
        for row in db.query(ArticleRegion.region_code)
        .filter(ArticleRegion.article_id == article_id)
        .all()
    }


def article_ids_with_regions(db: Session, article_ids: list[int]) -> set[int]:
    if not article_ids:
        return set()
    return {
        row[0]
        for row in db.query(ArticleRegion.article_id)
        .filter(ArticleRegion.article_id.in_(article_ids))
        .distinct()
        .all()
    }


def count_by_region(db: Session, since: datetime) -> list[tuple[str, str, int]]:
    """返回 (region_code, category, 文章数)，只统计窗口内的文章。"""
    rows = (
        db.query(ArticleRegion.region_code, Article.category,
                 func.count(ArticleRegion.id))
        .join(Article, Article.id == ArticleRegion.article_id)
        .filter(Article.fetched_at >= since)
        .group_by(ArticleRegion.region_code, Article.category)
        .all()
    )
    return [(row[0], row[1], row[2]) for row in rows]


def untagged_count(db: Session, since: datetime) -> int:
    tagged = db.query(ArticleRegion.article_id).distinct()
    return (
        db.query(func.count(Article.id))
        .filter(Article.fetched_at >= since, ~Article.id.in_(tagged))
        .scalar()
        or 0
    )


def list_articles_by_region(db: Session, *, code: str, since: datetime,
                            category: str | None = None,
                            limit: int = 30, offset: int = 0) -> list[Article]:
    query = (
        db.query(Article)
        .join(ArticleRegion, ArticleRegion.article_id == Article.id)
        .filter(ArticleRegion.region_code == code, Article.fetched_at >= since)
    )
    if category:
        query = query.filter(Article.category == category)
    return query.order_by(Article.fetched_at.desc()).offset(offset).limit(limit).all()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_article_regions.py -q`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/repositories/article_regions.py backend/tests/test_article_regions.py
git commit -m "feat(backend): 地区标签仓储与聚合查询"
```

---

## Task 4: 抽取顺带产出地区标签

**Files:**
- Modify: `backend/app/services/extraction/schemas.py`、`prompts.py`、`extractor.py`
- Test: `backend/tests/test_extractor.py`（在文件末尾追加）

- [ ] **Step 1: 写失败测试**

```python
# 追加到 backend/tests/test_extractor.py 末尾
def test_extract_writes_normalized_regions_and_drops_unknown(db):
    from app.core.config import Settings
    from app.repositories import article_regions as regions_repo

    art = _make_article(db, "military", "https://example.com/m-region")
    settings = Settings(_env_file=None)
    provider = FakeProvider(settings, {
        "category": "military",
        "military": {"weapons": [], "conflicts": [],
                     "regions": ["以色列", "加沙地带", "火星"]},
    })

    stats = extract_article(db, art, provider, settings)

    assert stats["failed"] == 0
    # 词表外的"火星"被丢弃，不落库
    assert regions_repo.codes_for_article(db, art.id) == {"il", "gaza"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_extractor.py -q`
Expected: FAIL —— `assert set() == {'il', 'gaza'}`

- [ ] **Step 3: 加字段、改提示词、写库**

`backend/app/services/extraction/schemas.py`：给 `PoliticsExtraction`、`MilitaryExtraction`、`EconomyExtraction`、`FinanceExtraction` 四个模型各加一个字段（位置放在各自第一个字段之前）：

```python
    regions: list[str] = []
```

`backend/app/services/extraction/prompts.py`：在 `build_extraction_prompt` 返回的字符串里、`events 数组`那一行之前插入一行：

```python
        "regions 数组（可留空）：新闻发生地，取值优先用国家名或热点区名"
        "（台海/加沙/南海/红海/北极）；可多个；判断不出发生地时给空数组。\n"
```

`backend/app/services/extraction/extractor.py`：

1. 顶部 import 增加

```python
from app.core.geo import normalize_region
from app.repositories import article_regions as article_regions_repo
```

2. 新增私有函数（放在 `_write_timeline` 之前）

```python
def _write_regions(db: Session, raw_regions: list[str], article_id: int) -> None:
    """归一化 LLM 给的地区名并落库；词表外的一律丢弃。"""
    codes = [code for code in (normalize_region(name) for name in raw_regions) if code]
    if not codes:
        return
    article_regions_repo.write_regions(db, article_id=article_id, codes=codes, source="llm")
```

3. 在 `parsed = model_cls.model_validate(payload)` 之后、`if category == "politics":` 之前插入

```python
        _write_regions(db, parsed.regions, article.id)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_extractor.py tests/test_extraction_rules.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/extraction backend/tests/test_extractor.py
git commit -m "feat(backend): 抽取顺带产出文章级地区标签"
```

---

## Task 5: 来源地区兜底

**Files:**
- Create: `backend/app/services/geo_tag.py`
- Modify: `backend/app/services/flow.py`
- Test: `backend/tests/test_flow.py`（在文件末尾追加）

- [ ] **Step 1: 写失败测试**

先在 `backend/tests/test_flow.py` 顶部把 `from datetime import datetime, timezone` 改成 `from datetime import datetime, timedelta, timezone`，再在文件末尾追加：

```python
def test_collect_flow_backfills_source_region(db):
    from app.core.config import Settings
    from app.models.entities import ArticleRegion
    from app.repositories import article_regions as regions_repo

    source = sources.create_source(
        db, name="Fixture", url="https://example.com/rss", feed_type="rss", lang="en",
        categories=[Category.economy.value, Category.finance.value],
    )
    source.region = "gb"
    db.commit()
    task = tasks.create_task(db, name="采集", kind="collect", category=None,
                             cron="0 */4 * * *")
    settings = Settings(_env_file=None, extract_enabled=False)

    result = run_task_flow(db, task, client=_feed_client(),
                           provider=FakeProvider(settings), settings=settings)

    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    assert result["status"] == "success"
    assert regions_repo.untagged_count(db, since) == 0  # 抽取关闭也要有标签
    assert {row[0] for row in regions_repo.count_by_region(db, since)} == {"gb"}
    assert {row[0] for row in db.query(ArticleRegion.source).all()} == {"source"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_flow.py -q -k backfill`
Expected: FAIL —— `assert 2 == 0`（未打标的文章有 2 篇）

- [ ] **Step 3: 实现兜底并接入流程**

```python
# backend/app/services/geo_tag.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import Article
from app.repositories import article_regions as article_regions_repo


def backfill_source_regions(db: Session, articles: list[Article]) -> int:
    """给还没有任何地区标签的文章补一条来源地区标签，返回补标条数。

    只兜底、不覆盖：已有标签的文章跳过；来源没配 region 的文章保持未标注。
    """
    if not articles:
        return 0
    tagged = article_regions_repo.article_ids_with_regions(db, [a.id for a in articles])
    created = 0
    for article in articles:
        if article.id in tagged:
            continue
        code = (article.source.region if article.source else "") or ""
        if not code:
            continue
        created += article_regions_repo.write_regions(
            db, article_id=article.id, codes=[code], source="source"
        )
    return created
```

`backend/app/services/flow.py`：把采集分支里的抽取块整体替换成下面这段（先取一次新文章列表，抽取与兜底共用）：

```python
            new_articles = articles_repo.list_new_since(db, started) if new else []
            if new_articles and settings.extract_enabled:
                prov = provider or get_provider(settings)
                for article in new_articles:
                    try:
                        stats = extract_article(db, article, prov, settings)
                        if stats["failed"]:
                            errors.append(f"文章 {article.id} 提取失败 {stats['failed']} 项")
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"文章 {article.id} 提取异常: {exc}")
            if new_articles:
                try:
                    backfill_source_regions(db, new_articles)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"地区兜底失败: {exc}")
```

并在 `flow.py` 顶部加 import：

```python
from app.services.geo_tag import backfill_source_regions
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_flow.py -q`
Expected: PASS（含既有 5 个用例）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/geo_tag.py backend/app/services/flow.py backend/tests/test_flow.py
git commit -m "feat(backend): 来源地区兜底补标"
```

---

## Task 6: 聚合接口与地区文章接口

**Files:**
- Create: `backend/app/api/serializers.py`、`backend/app/api/routes_geo.py`
- Modify: `backend/app/api/routes_articles.py`、`backend/app/main.py`
- Test: `backend/tests/test_api_geo.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_api_geo.py
from datetime import datetime, timezone

from app.models.entities import Category
from app.repositories import article_regions as regions_repo
from app.repositories import articles as articles_repo
from app.repositories import sources as sources_repo


def _seed(client):
    with client.app.state.session_factory() as db:
        source = sources_repo.create_source(
            db, name="S", url="https://example.com/rss", feed_type="rss", lang="en",
            categories=[Category.politics.value, Category.finance.value],
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        articles_repo.insert_articles(db, [
            dict(source_id=source.id, category="politics", url="https://example.com/1",
                 title="中东议题", summary="s", content_text="", published_at=now,
                 lang="en", dedupe_hash="g1"),
            dict(source_id=source.id, category="finance", url="https://example.com/2",
                 title="红海运费", summary="s", content_text="", published_at=now,
                 lang="en", dedupe_hash="g2"),
            dict(source_id=source.id, category="finance", url="https://example.com/3",
                 title="无地区", summary="s", content_text="", published_at=now,
                 lang="en", dedupe_hash="g3"),
        ])
        by_hash = {a.dedupe_hash: a for a in articles_repo.list_articles(db)}
        regions_repo.write_regions(db, article_id=by_hash["g1"].id, codes=["il", "gaza"])
        regions_repo.write_regions(db, article_id=by_hash["g2"].id, codes=["il"])


def test_dashboard_geo_aggregates_by_region_and_category(client):
    _seed(client)
    body = client.get("/api/dashboard/geo?window=24h").json()

    assert body["window"] == "24h"
    assert body["total"] == 3
    assert body["untagged"] == 1
    assert body["regions"][0]["code"] == "il"  # 按 count 倒序

    israel = next(r for r in body["regions"] if r["code"] == "il")
    assert israel["name"] == "以色列"
    assert israel["count"] == 2
    assert israel["by_category"]["politics"] == 1
    assert israel["by_category"]["finance"] == 1
    assert israel["by_category"]["military"] == 0

    gaza = next(r for r in body["regions"] if r["code"] == "gaza")
    assert gaza["count"] == 1 and gaza["by_category"]["politics"] == 1


def test_dashboard_geo_rejects_unknown_window(client):
    assert client.get("/api/dashboard/geo?window=1h").status_code == 422


def test_region_articles_endpoint(client):
    _seed(client)
    body = client.get("/api/regions/il/articles").json()
    assert body["name"] == "以色列"
    assert len(body["items"]) == 2

    finance_only = client.get("/api/regions/il/articles?category=finance").json()
    assert [item["title"] for item in finance_only["items"]] == ["红海运费"]
    assert client.get("/api/regions/nowhere/articles").status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_api_geo.py -q`
Expected: FAIL —— 404（路由还不存在）

- [ ] **Step 3: 抽出共享序列化器**

```python
# backend/app/api/serializers.py
from app.models.entities import Article


def article_out(article: Article) -> dict:
    return {
        "id": article.id,
        "category": article.category,
        "title": article.title,
        "url": article.url,
        "summary": article.summary,
        "source_name": article.source.name if article.source else None,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "fetched_at": article.fetched_at.isoformat(),
        "lang": article.lang,
    }
```

`backend/app/api/routes_articles.py`：删掉本文件里的 `_out()`，改用共享序列化器（行为不变，既有测试覆盖）。

```python
from app.api.serializers import article_out
```

并把两个用到 `_out(...)` 的地方改成 `article_out(...)`（`get_article` 里那处写成 `{**article_out(article), "content_text": article.content_text}`）。

- [ ] **Step 4: 实现接口**

```python
# backend/app/api/routes_geo.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.serializers import article_out
from app.core.constants import ALL_CATEGORIES
from app.core.geo import REGION_MAP
from app.repositories import article_regions as article_regions_repo
from app.repositories import articles as articles_repo

router = APIRouter(prefix="/api", tags=["geo"])

WINDOW_HOURS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}


def window_start(window: str) -> datetime:
    hours = WINDOW_HOURS.get(window)
    if hours is None:
        raise HTTPException(status_code=422, detail="window 仅支持 24h / 7d / 30d")
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)


@router.get("/dashboard/geo")
def dashboard_geo(window: str = Query(default="24h"),
                  db: Session = Depends(get_db)) -> dict:
    since = window_start(window)
    buckets: dict[str, dict] = {}
    for code, category, count in article_regions_repo.count_by_region(db, since):
        entry = buckets.setdefault(
            code, {"count": 0, "by_category": {c: 0 for c in ALL_CATEGORIES}}
        )
        entry["count"] += count
        entry["by_category"][category] = entry["by_category"].get(category, 0) + count

    regions = []
    for code, entry in buckets.items():
        info = REGION_MAP.get(code)
        if info is None:  # 词表里被删掉的历史标签，跳过而不是报错
            continue
        regions.append({
            "code": code, "name": info["name_zh"],
            "lng": info["lng"], "lat": info["lat"],
            "count": entry["count"], "by_category": entry["by_category"],
        })
    regions.sort(key=lambda item: (-item["count"], item["code"]))
    return {
        "window": window,
        "window_start": since.isoformat(),
        "total": articles_repo.count_all_since(db, since),
        "untagged": article_regions_repo.untagged_count(db, since),
        "regions": regions,
    }


@router.get("/regions/{code}/articles")
def region_articles(code: str, window: str = Query(default="24h"),
                    category: str | None = None,
                    limit: int = Query(default=30, le=100),
                    offset: int = Query(default=0, ge=0),
                    db: Session = Depends(get_db)) -> dict:
    info = REGION_MAP.get(code)
    if info is None:
        raise HTTPException(status_code=404, detail="未知地区")
    since = window_start(window)
    items = article_regions_repo.list_articles_by_region(
        db, code=code, since=since, category=category, limit=limit, offset=offset
    )
    return {"region": code, "name": info["name_zh"], "window": window,
            "items": [article_out(article) for article in items]}
```

`backend/app/main.py`：在 import 列表里加 `routes_geo`，并在其它 `include_router` 之后加一行

```python
    app.include_router(routes_geo.router)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_api_geo.py tests/test_api_content.py -q`
Expected: PASS（含既有文章接口用例，验证序列化器抽离无回归）

- [ ] **Step 6: 提交**

```bash
git add backend/app/api/serializers.py backend/app/api/routes_geo.py \
        backend/app/api/routes_articles.py backend/app/main.py backend/tests/test_api_geo.py
git commit -m "feat(backend): 地区聚合接口与地区文章接口"
```

---

## Task 7: 采集源地区字段与地区选项接口

**Files:**
- Modify: `backend/app/repositories/sources.py`、`backend/app/api/routes_sources.py`、`backend/app/api/routes_geo.py`
- Test: `backend/tests/test_api_sources.py`（文件末尾追加）

- [ ] **Step 1: 写失败测试**

```python
def test_source_region_roundtrip(client):
    body = {
        "name": "Region Feed", "url": "https://region.example/feed",
        "feed_type": "rss", "lang": "en", "categories": ["politics"], "region": "gb",
    }
    created = client.post("/api/sources", json=body)
    assert created.status_code == 201
    assert created.json()["region"] == "gb"

    source_id = created.json()["id"]
    patched = client.patch(f"/api/sources/{source_id}", json={"region": "us"})
    assert patched.json()["region"] == "us"

    options = client.get("/api/regions").json()["items"]
    assert {"code": "us", "name": "美国"} in options
    assert {"code": "gaza", "name": "加沙"} in options
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_api_sources.py -q -k region`
Expected: FAIL —— `KeyError: 'region'`

- [ ] **Step 3: 打通仓储与接口**

`backend/app/repositories/sources.py` 的 `create_source` 增加参数并写入：

```python
def create_source(db: Session, *, name: str, url: str, feed_type: str, lang: str,
                  categories: list[str], region: str = "",
                  enabled: bool = True) -> Source:
    source = Source(name=name, url=url, feed_type=feed_type, lang=lang,
                    region=region, enabled=enabled)
```

`update_source` 增加参数与赋值：

```python
                  lang: str | None = None, enabled: bool | None = None,
                  region: str | None = None,
                  categories: list[str] | None = None) -> Source:
```

```python
    if region is not None:
        source.region = region
```

`backend/app/api/routes_sources.py`：

- `SourceIn` 增加 `region: str = Field(default="", max_length=32)`
- `SourcePatch` 增加 `region: str | None = Field(default=None, max_length=32)`
- `_out()` 增加 `"region": source.region,`
- `create_source` / `patch_source` 两个路由把 `region=payload.region` 传给仓储

`backend/app/api/routes_geo.py` 增加地区选项接口（前端下拉与图例共用，避免在前端复制词表）：

```python
from app.core.geo import REGIONS


@router.get("/regions")
def list_regions() -> dict:
    return {"items": [{"code": r["code"], "name": r["name_zh"]}
                      for r in sorted(REGIONS, key=lambda r: r["code"])]}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_api_sources.py tests/test_api_geo.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/repositories/sources.py backend/app/api/routes_sources.py backend/app/api/routes_geo.py backend/tests/test_api_sources.py
git commit -m "feat(backend): 采集源地区字段与地区选项接口"
```

---

## Task 8: 前端依赖与离线底图资产

**Files:**
- Create: `frontend/scripts/build-world-geo.mjs`、`frontend/src/assets/world.geo.json`、`backend/tests/test_geo_asset.py`
- Modify: `frontend/package.json`（npm 写入）

- [ ] **Step 1: 安装 ECharts**

```bash
cd frontend && npm install echarts
```

Expected: `dependencies` 出现 `echarts`

- [ ] **Step 2: 下载 Natural Earth 原始底图**

```bash
curl -fsSL -o /tmp/ne_110m_countries.geojson https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson
ls -la /tmp/ne_110m_countries.geojson
```

Expected: 文件存在，约 3-8 MB

- [ ] **Step 3: 写转换脚本**

```js
// frontend/scripts/build-world-geo.mjs
// 用法：node scripts/build-world-geo.mjs <原始 ne_110m geojson> [输出路径]
// 产出的 properties.name = 地区 code，供 ECharts 按 code 着色；
// 与后端 app/core/geo.py 的一致性由 backend/tests/test_geo_asset.py 守护。
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

const [, , source, target = "src/assets/world.geo.json"] = process.argv;
if (!source) {
  console.error("用法：node scripts/build-world-geo.mjs <原始 geojson> [输出路径]");
  process.exit(1);
}

const round = (value) => Math.round(value * 100) / 100;
const roundCoords = (node) =>
  Array.isArray(node[0]) ? node.map(roundCoords) : [round(node[0]), round(node[1])];

const raw = JSON.parse(readFileSync(source, "utf-8"));
const features = raw.features
  .map((feature) => {
    const props = feature.properties ?? {};
    // ISO_A2 在 Natural Earth 里对法国/挪威等是 "-99"，优先用 ISO_A2_EH
    const code = String(props.ISO_A2_EH ?? props.ISO_A2 ?? "").toLowerCase();
    if (!/^[a-z]{2}$/.test(code)) return null;
    return {
      type: "Feature",
      properties: { name: code, name_zh: props.NAME_ZH ?? "" },
      geometry: {
        type: feature.geometry.type,
        coordinates: roundCoords(feature.geometry.coordinates),
      },
    };
  })
  .filter(Boolean);

mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, JSON.stringify({ type: "FeatureCollection", features }));
console.log(`写出 ${features.length} 个国家的边界 → ${target}`);
```

- [ ] **Step 4: 生成资产并检查体积**

```bash
cd frontend && node scripts/build-world-geo.mjs /tmp/ne_110m_countries.geojson
ls -la src/assets/world.geo.json
```

Expected: 打印国家数量（170 左右），文件 < 200KB

- [ ] **Step 5: 写一致性测试**

```python
# backend/tests/test_geo_asset.py
import json
from pathlib import Path

from app.core.geo import COUNTRIES

ASSET = Path(__file__).resolve().parents[2] / "frontend" / "src" / "assets" / "world.geo.json"


def test_asset_covers_every_country():
    payload = json.loads(ASSET.read_text(encoding="utf-8"))
    codes = {feature["properties"]["name"] for feature in payload["features"]}
    missing = [country["code"] for country in COUNTRIES if country["code"] not in codes]
    assert missing == [], f"这些国家在底图里没有几何，地图上会点不出来：{missing}"
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_geo_asset.py -q`
Expected: PASS（FAIL 说明词表 code 写错或底图缺该国，按报错补齐）

- [ ] **Step 7: 提交**

```bash
git add frontend/package.json frontend/package-lock.json frontend/scripts/build-world-geo.mjs frontend/src/assets/world.geo.json backend/tests/test_geo_asset.py
git commit -m "feat(frontend): 引入 echarts 与离线世界底图资产"
```

---

## Task 9: 前端地区常量与纯函数

**Files:**
- Create: `frontend/src/constants/geo.ts`、`frontend/src/utils/geo.ts`
- Test: `frontend/src/utils/geo.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
// frontend/src/utils/geo.test.ts
import { describe, expect, it } from "vitest";

import type { GeoRegion } from "../api/types";
import { HEAT_COLORS } from "../constants/geo";
import { buildHeatScale, countFor, filterRegions, pointSize, regionPoints } from "./geo";

function region(code: string, byCategory: Record<string, number>): GeoRegion {
  return {
    code,
    name: code,
    lng: 10,
    lat: 20,
    count: Object.values(byCategory).reduce((sum, value) => sum + value, 0),
    by_category: { politics: 0, economy: 0, finance: 0, military: 0, ...byCategory },
  };
}

describe("countFor / filterRegions", () => {
  it("只累计被选中的板块", () => {
    const item = region("il", { politics: 3, military: 6, finance: 1 });
    expect(countFor(item, ["politics", "military"])).toBe(9);
    expect(countFor(item, ["economy"])).toBe(0);
  });

  it("筛选后 count 用重算值，为 0 的地区被丢掉", () => {
    const filtered = filterRegions([region("il", { military: 6 }), region("us", { finance: 2 })],
                                  ["military"]);
    expect(filtered.map((item) => item.code)).toEqual(["il"]);
    expect(filtered[0].count).toBe(6);
  });
});

describe("buildHeatScale", () => {
  it("只有一种数值时返回中间档，空数组返回最浅档", () => {
    expect(buildHeatScale([4, 4])(4)).toBe(HEAT_COLORS[Math.floor(HEAT_COLORS.length / 2)]);
    expect(buildHeatScale([])(3)).toBe(HEAT_COLORS[0]);
  });

  it("按数值排名分档，单个超热地区不会把其余压成最浅档", () => {
    const scale = buildHeatScale([1, 1, 1, 1, 10]);
    expect(scale(1)).toBe(HEAT_COLORS[0]);
    expect(scale(10)).toBe(HEAT_COLORS[HEAT_COLORS.length - 1]);
  });

  it("中间值落在中间档", () => {
    const scale = buildHeatScale([1, 2, 3, 4, 5]);
    expect(scale(3)).toBe(HEAT_COLORS[Math.round((2 / 4) * (HEAT_COLORS.length - 1))]);
  });
});

describe("regionPoints", () => {
  it("按板块逐地区展开，只保留有量的板块并做偏移", () => {
    const points = regionPoints([region("il", { politics: 3, military: 6 })],
                                ["politics", "economy", "finance", "military"]);
    expect(points.map((point) => point.category)).toEqual(["politics", "military"]);
    expect(points[0]).toMatchObject({ code: "il", count: 3 });
    expect(points[1].lng).not.toBe(points[0].lng);
  });
});

describe("pointSize", () => {
  it("把条数线性映射到最小与最大之间", () => {
    expect(pointSize(0, 10)).toBe(5);
    expect(pointSize(10, 10)).toBe(14);
    expect(pointSize(5, 10)).toBeGreaterThan(5);
    expect(pointSize(3, 1)).toBe(5);
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npm test`
Expected: FAIL —— 解析不到 `./geo`

- [ ] **Step 3: 写常量与纯函数**

```ts
// frontend/src/constants/geo.ts
import type { CategoryKey } from "./categories";

export type GeoWindow = "24h" | "7d" | "30d";

export const GEO_WINDOWS: { label: string; value: GeoWindow }[] = [
  { label: "24 小时", value: "24h" },
  { label: "7 天", value: "7d" },
  { label: "30 天", value: "30d" },
];

export function windowLabel(value: GeoWindow): string {
  return GEO_WINDOWS.find((item) => item.value === value)?.label ?? value;
}

// 热度分档：浅 → 深；分档算法在 utils/geo.ts
export const HEAT_COLORS = ["#e8eefb", "#cfe0fb", "#a9c8f5", "#7aa7ec", "#4a80dd", "#2563eb"];
export const EMPTY_AREA_COLOR = "#eef1f6";
export const SELECTED_AREA_COLOR = "#fdd9a0";

// 同一地区最多 4 个点：按板块固定偏移，避免坐标完全重叠
export const CATEGORY_OFFSETS: Record<CategoryKey, [number, number]> = {
  politics: [0, 0],
  economy: [0.75, 0.75],
  finance: [-0.75, 0.75],
  military: [0.75, -0.75],
};

export const POINT_SIZE = { min: 5, max: 14 } as const;

export const GEO_TEXT = {
  empty: "暂无地理标注数据，请先执行采集任务",
  untagged: (count: number) => `未定位 ${count} 条`,
  rankingTitle: "地区榜",
  backToRanking: "← 返回地区榜",
  regionTitle: (name: string, window: string) => `${name} · 近 ${window}`,
  legendHint: "点击图例可只看某一类",
} as const;
```

```ts
// frontend/src/utils/geo.ts
import type { GeoRegion } from "../api/types";
import { CATEGORY_OFFSETS, HEAT_COLORS, POINT_SIZE } from "../constants/geo";

export interface MapPoint {
  code: string;
  name: string;
  category: string;
  count: number;
  lng: number;
  lat: number;
}

export function countFor(region: GeoRegion, categories: string[]): number {
  return categories.reduce((sum, key) => sum + (region.by_category[key] ?? 0), 0);
}

/** 按所选板块重算 count，并丢掉重算后为 0 的地区。 */
export function filterRegions(regions: GeoRegion[], categories: string[]): GeoRegion[] {
  return regions
    .map((region) => ({ ...region, count: countFor(region, categories) }))
    .filter((region) => region.count > 0);
}

/** 按不同数值的排名分档，避免单个超热地区把其余国家压成最浅一档。 */
export function buildHeatScale(counts: number[]): (count: number) => string {
  const distinct = Array.from(new Set(counts.filter((count) => count > 0))).sort((a, b) => a - b);
  if (distinct.length === 0) return () => HEAT_COLORS[0];
  if (distinct.length === 1) return () => HEAT_COLORS[Math.floor(HEAT_COLORS.length / 2)];
  const step = HEAT_COLORS.length - 1;
  return (count: number) => {
    if (count <= 0) return HEAT_COLORS[0];
    const index = distinct.indexOf(count);
    if (index < 0) return HEAT_COLORS[HEAT_COLORS.length - 1];
    return HEAT_COLORS[Math.round((index / (distinct.length - 1)) * step)];
  };
}

/** 把「地区 × 板块」展开成散点：同地区不同板块坐标做固定偏移。 */
export function regionPoints(regions: GeoRegion[], categories: string[]): MapPoint[] {
  const points: MapPoint[] = [];
  for (const region of regions) {
    for (const key of categories) {
      const count = region.by_category[key] ?? 0;
      if (count <= 0) continue;
      const offset = CATEGORY_OFFSETS[key as keyof typeof CATEGORY_OFFSETS] ?? [0, 0];
      points.push({
        code: region.code,
        name: region.name,
        category: key,
        count,
        lng: region.lng + offset[0],
        lat: region.lat + offset[1],
      });
    }
  }
  return points;
}

export function pointSize(count: number, max: number): number {
  if (max <= 1) return POINT_SIZE.min;
  const ratio = Math.min(1, Math.max(0, count / max));
  return POINT_SIZE.min + ratio * (POINT_SIZE.max - POINT_SIZE.min);
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npm test`
Expected: PASS（含既有 `format.test.ts`、`moderation.test.ts`）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/constants/geo.ts frontend/src/utils/geo.ts frontend/src/utils/geo.test.ts
git commit -m "feat(frontend): 地区常量与地图纯函数"
```

---

## Task 10: 前端 API 层

**Files:**
- Modify: `frontend/src/api/types.ts`、`frontend/src/api/endpoints.ts`

- [ ] **Step 1: 加类型**

追加到 `frontend/src/api/types.ts`：

```ts
export interface GeoRegion {
  code: string;
  name: string;
  lng: number;
  lat: number;
  count: number;
  by_category: Record<string, number>;
}

export interface GeoOverview {
  window: string;
  window_start: string;
  total: number;
  untagged: number;
  regions: GeoRegion[];
}

export interface RegionArticles {
  region: string;
  name: string;
  window: string;
  items: ArticleItem[];
}

export interface RegionOption {
  code: string;
  name: string;
}
```

并给 `SourceItem` 与 `SourceInput` 各加一行 `region: string;`。

- [ ] **Step 2: 加端点**

`frontend/src/api/endpoints.ts`：顶部 import 增加

```ts
import type { GeoWindow } from "../constants/geo";
import type { GeoOverview, RegionArticles, RegionOption } from "./types";
```

`api` 对象里增加：

```ts
  geo: (window: GeoWindow) => http.get<GeoOverview>(`/dashboard/geo${queryString({ window })}`),
  regions: () => http.get<{ items: RegionOption[] }>("/regions"),
  regionArticles: (code: string, params: { window: GeoWindow; category?: string; limit?: number }) =>
    http.get<RegionArticles>(`/regions/${code}/articles${queryString(params)}`),
```

- [ ] **Step 3: 跑类型检查**

Run: `cd frontend && npm run typecheck`
Expected: PASS（若报 `SourceInput` 缺 `region`，在 `SourcesPage.tsx` 的 `EMPTY_FORM` 里补 `region: ""`，Task 16 会接上完整 UI）

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/types.ts frontend/src/api/endpoints.ts
git commit -m "feat(frontend): 地区接口类型与端点"
```

---

## Task 11: 地图组件 WorldMap

**Files:**
- Create: `frontend/src/components/map/WorldMap.tsx`

说明：组件是渲染层，仓库的 vitest 只跑纯函数（`vite.config.ts` 里 `include: ["src/**/*.test.ts"]`、environment=node），所以本任务用类型检查 + 手动查看验证，不给组件补测试。

- [ ] **Step 1: 写组件**

```tsx
// frontend/src/components/map/WorldMap.tsx
import { MapChart, ScatterChart } from "echarts/charts";
import { GeoComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef } from "react";

import type { GeoRegion } from "../../api/types";
import worldGeo from "../../assets/world.geo.json";
import { CATEGORY_MAP } from "../../constants/categories";
import type { CategoryKey } from "../../constants/categories";
import { EMPTY_AREA_COLOR, SELECTED_AREA_COLOR } from "../../constants/geo";
import type { MapPoint } from "../../utils/geo";
import { buildHeatScale, pointSize, regionPoints } from "../../utils/geo";

echarts.use([MapChart, ScatterChart, GeoComponent, TooltipComponent, CanvasRenderer]);
echarts.registerMap("world", worldGeo as never);

interface Props {
  regions: GeoRegion[];
  categories: string[];
  selected: string | null;
  onSelect: (code: string) => void;
  loading?: boolean;
}

export default function WorldMap({
  regions,
  categories,
  selected,
  onSelect,
  loading = false,
}: Props) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ReturnType<typeof echarts.init> | null>(null);
  const handlerRef = useRef(onSelect);
  handlerRef.current = onSelect;

  const option = useMemo(() => {
    const heat = buildHeatScale(regions.map((region) => region.count));
    const max = Math.max(1, ...regions.map((region) => region.count));
    const points = regionPoints(regions, categories);
    const regionByCode = new Map(regions.map((region) => [region.code, region]));

    return {
      tooltip: {
        trigger: "item" as const,
        formatter: (params: { seriesType?: string; name?: string; data?: unknown }) => {
          const point = params.data as MapPoint | undefined;
          if (params.seriesType === "scatter" && point) {
            const label = CATEGORY_MAP[point.category as CategoryKey]?.label ?? point.category;
            return `${point.name}<br/>${label} · ${point.count} 条`;
          }
          const region = regionByCode.get(params.name ?? "");
          return region ? `${region.name}<br/>共 ${region.count} 条` : params.name ?? "";
        },
      },
      geo: {
        map: "world",
        roam: true,
        itemStyle: { areaColor: EMPTY_AREA_COLOR, borderColor: "#dbe2ee", borderWidth: 0.5 },
        emphasis: { itemStyle: { areaColor: "#c7dbf8" }, label: { show: false } },
        select: { disabled: true },
      },
      series: [
        {
          type: "map" as const,
          geoIndex: 0,
          data: regions.map((region) => ({
            name: region.code,
            value: region.count,
            itemStyle: {
              areaColor: region.code === selected ? SELECTED_AREA_COLOR : heat(region.count),
            },
          })),
        },
        {
          type: "scatter" as const,
          coordinateSystem: "geo" as const,
          symbolSize: (value: number[]) => pointSize(value[2], max),
          itemStyle: { opacity: 0.8, borderColor: "#fff", borderWidth: 0.6 },
          data: points.map((point) => ({
            ...point,
            value: [point.lng, point.lat, point.count],
            itemStyle: {
              color: CATEGORY_MAP[point.category as CategoryKey]?.color ?? "#64748b",
            },
          })),
        },
      ],
    };
  }, [regions, categories, selected]);

  useEffect(() => {
    if (!hostRef.current) return;
    const chart = echarts.init(hostRef.current);
    chartRef.current = chart;
    chart.on("click", (params: { seriesType?: string; name?: string; data?: unknown }) => {
      const point = params.data as MapPoint | undefined;
      const code = params.seriesType === "scatter" ? point?.code : params.name;
      if (code) handlerRef.current(code);
    });
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, true);
  }, [option]);

  return (
    <div style={{ position: "relative", height: 520 }}>
      <div ref={hostRef} style={{ width: "100%", height: "100%" }} />
      {loading ? (
        <span className="aurora-muted" style={{ position: "absolute", top: 8, left: 8 }}>
          加载中…
        </span>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npm run typecheck`
Expected: PASS（若 `worldGeo as never` 仍报错，改成 `echarts.registerMap("world", worldGeo as unknown as Parameters<typeof echarts.registerMap>[1])`）

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/map/WorldMap.tsx
git commit -m "feat(frontend): 双层世界地图组件"
```

---

## Task 12: 图例与时间窗 MapLegend

**Files:**
- Create: `frontend/src/components/map/MapLegend.tsx`

- [ ] **Step 1: 写组件**

```tsx
// frontend/src/components/map/MapLegend.tsx
import { Segmented, Space, Tooltip, Typography } from "antd";

import { CATEGORIES } from "../../constants/categories";
import { GEO_TEXT, GEO_WINDOWS } from "../../constants/geo";
import type { GeoWindow } from "../../constants/geo";

interface Props {
  windowKey: GeoWindow;
  onWindowChange: (value: GeoWindow) => void;
  activeCategories: string[];
  onToggleCategory: (key: string) => void;
  untagged: number;
}

export default function MapLegend({
  windowKey,
  onWindowChange,
  activeCategories,
  onToggleCategory,
  untagged,
}: Props) {
  return (
    <Space size={12} wrap style={{ width: "100%", justifyContent: "space-between" }}>
      <Space size={14} wrap>
        {CATEGORIES.map((category) => {
          const active = activeCategories.includes(category.key);
          return (
            <Tooltip key={category.key} title={GEO_TEXT.legendHint}>
              <span
                onClick={() => onToggleCategory(category.key)}
                style={{
                  cursor: "pointer",
                  opacity: active ? 1 : 0.35,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5,
                  fontSize: 13,
                }}
              >
                <i
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    background: category.color,
                    display: "inline-block",
                  }}
                />
                {category.label}
              </span>
            </Tooltip>
          );
        })}
        {untagged > 0 ? (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {GEO_TEXT.untagged(untagged)}
          </Typography.Text>
        ) : null}
      </Space>
      <Segmented
        value={windowKey}
        options={GEO_WINDOWS}
        onChange={(value) => onWindowChange(value as GeoWindow)}
      />
    </Space>
  );
}
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npm run typecheck`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/map/MapLegend.tsx
git commit -m "feat(frontend): 地图图例与时间窗切换"
```

---

## Task 13: 右栏面板 RegionPanel

**Files:**
- Create: `frontend/src/components/map/RegionPanel.tsx`

- [ ] **Step 1: 写组件**

```tsx
// frontend/src/components/map/RegionPanel.tsx
import { Button, Card, List, Space, Tag } from "antd";

import { api } from "../../api/endpoints";
import type { GeoRegion } from "../../api/types";
import { CATEGORY_MAP } from "../../constants/categories";
import type { CategoryKey } from "../../constants/categories";
import { GEO_TEXT, windowLabel } from "../../constants/geo";
import type { GeoWindow } from "../../constants/geo";
import { useAsync } from "../../hooks/useAsync";
import { formatDateTime } from "../../utils/format";
import EmptyHint from "../EmptyHint";

interface Props {
  regions: GeoRegion[];
  windowKey: GeoWindow;
  selected: string | null;
  onSelect: (code: string | null) => void;
  loading?: boolean;
}

export default function RegionPanel({
  regions,
  windowKey,
  selected,
  onSelect,
  loading = false,
}: Props) {
  const detail = useAsync(
    () => (selected ? api.regionArticles(selected, { window: windowKey, limit: 30 }) : Promise.resolve(null)),
    [selected, windowKey],
  );

  if (!selected) {
    return (
      <Card size="small" variant="outlined" title={GEO_TEXT.rankingTitle} loading={loading}>
        {regions.length === 0 ? (
          <EmptyHint text={GEO_TEXT.empty} compact />
        ) : (
          <List
            size="small"
            dataSource={regions.slice(0, 12)}
            renderItem={(region, index) => (
              <List.Item style={{ cursor: "pointer" }} onClick={() => onSelect(region.code)}>
                <Space size={8} style={{ width: "100%" }}>
                  <Tag>{index + 1}</Tag>
                  <span style={{ flex: 1 }}>{region.name}</span>
                  <span className="aurora-muted">{region.count}</span>
                </Space>
              </List.Item>
            )}
          />
        )}
      </Card>
    );
  }

  const items = detail.data?.items ?? [];
  return (
    <Card
      size="small"
      variant="outlined"
      loading={detail.loading}
      title={GEO_TEXT.regionTitle(detail.data?.name ?? selected, windowLabel(windowKey))}
      extra={
        <Button type="link" size="small" onClick={() => onSelect(null)}>
          {GEO_TEXT.backToRanking}
        </Button>
      }
    >
      {items.length === 0 ? (
        <EmptyHint text="该地区在时间窗内没有文章" compact />
      ) : (
        <List
          size="small"
          dataSource={items}
          renderItem={(item) => {
            const meta = CATEGORY_MAP[item.category as CategoryKey];
            return (
              <List.Item>
                <List.Item.Meta
                  title={
                    <a href={item.url} target="_blank" rel="noreferrer">
                      {item.title}
                    </a>
                  }
                  description={
                    <span className="aurora-muted">
                      <Tag color={meta?.color}>{meta?.label ?? item.category}</Tag>
                      {item.source_name ?? "未知来源"} ·{" "}
                      {formatDateTime(item.published_at ?? item.fetched_at)}
                    </span>
                  }
                />
              </List.Item>
            );
          }}
        />
      )}
    </Card>
  );
}
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npm run typecheck`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/map/RegionPanel.tsx
git commit -m "feat(frontend): 地区榜与地区新闻两态面板"
```

---

## Task 14: 板块 chip 条 CategoryStrip

**Files:**
- Create: `frontend/src/components/map/CategoryStrip.tsx`

作用：`DashboardPage` 删除后，原四张板块卡的「最新日报标题 + 近 24h 条数」由这条 chip 承接。

- [ ] **Step 1: 写组件**

```tsx
// frontend/src/components/map/CategoryStrip.tsx
import { Card, Space, Tooltip } from "antd";
import { Link } from "react-router-dom";

import type { CategoryOverview } from "../../api/types";
import { CATEGORIES } from "../../constants/categories";

interface Props {
  overview: CategoryOverview[];
}

export default function CategoryStrip({ overview }: Props) {
  const byCategory = new Map(overview.map((item) => [item.category, item]));
  return (
    <Card size="small" variant="outlined" styles={{ body: { padding: 10 } }}>
      <Space size={20} wrap>
        {CATEGORIES.map((category) => {
          const item = byCategory.get(category.key);
          const tooltip = item?.latest_daily_title ?? `${category.label}今日报告尚未生成`;
          return (
            <Tooltip key={category.key} title={tooltip}>
              <Link
                to={category.path}
                style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13 }}
              >
                <i
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 3,
                    background: category.color,
                    display: "inline-block",
                  }}
                />
                {category.label}
                <span className="aurora-muted">近 24h {item?.article_count ?? 0} 篇</span>
              </Link>
            </Tooltip>
          );
        })}
      </Space>
    </Card>
  );
}
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npm run typecheck`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/map/CategoryStrip.tsx
git commit -m "feat(frontend): 板块状态 chip 条"
```

---

## Task 15: 看板页面与路由替换

**Files:**
- Create: `frontend/src/pages/MapBoardPage.tsx`
- Modify: `frontend/src/App.tsx`
- Delete: `frontend/src/pages/DashboardPage.tsx`

- [ ] **Step 1: 写页面**

```tsx
// frontend/src/pages/MapBoardPage.tsx
import { Card, Col, Row } from "antd";
import { useMemo, useState } from "react";

import { api } from "../api/endpoints";
import EmptyHint from "../components/EmptyHint";
import PageHeader from "../components/PageHeader";
import StatCards from "../components/StatCards";
import CategoryStrip from "../components/map/CategoryStrip";
import MapLegend from "../components/map/MapLegend";
import RegionPanel from "../components/map/RegionPanel";
import WorldMap from "../components/map/WorldMap";
import { CATEGORIES } from "../constants/categories";
import type { GeoWindow } from "../constants/geo";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime } from "../utils/format";
import { filterRegions } from "../utils/geo";

const ALL_CATEGORY_KEYS = CATEGORIES.map((category) => category.key);

export default function MapBoardPage() {
  const [windowKey, setWindowKey] = useState<GeoWindow>("24h");
  const [selected, setSelected] = useState<string | null>(null);
  const [activeCategories, setActiveCategories] = useState<string[]>(ALL_CATEGORY_KEYS);

  const dashboard = useAsync(() => api.dashboard(), []);
  const overview = useAsync(() => api.categories(), []);
  const geo = useAsync(() => api.geo(windowKey), [windowKey]);

  const summary = dashboard.data;
  const visibleRegions = useMemo(
    () => filterRegions(geo.data?.regions ?? [], activeCategories),
    [geo.data, activeCategories],
  );

  function toggleCategory(key: string) {
    setActiveCategories((current) => {
      const next = current.includes(key)
        ? current.filter((item) => item !== key)
        : [...current, key];
      return next.length === 0 ? current : next; // 至少留一类，避免空图
    });
  }

  function changeWindow(value: GeoWindow) {
    setWindowKey(value);
    setSelected(null);
  }

  return (
    <div className="aurora-stack">
      <PageHeader
        title="世界看板"
        tagline="全球政治 · 经济 · 金融 · 军事信息收集与分析"
      />
      <StatCards
        items={[
          { label: "今日新增文章", value: summary?.today_articles ?? 0 },
          { label: "今日生成分析", value: summary?.today_analyses ?? 0 },
          {
            label: "源健康",
            value: summary
              ? `${summary.source_health.healthy}/${summary.source_health.enabled}`
              : "—",
            hint: "健康 / 启用",
          },
          {
            label: "下次定时任务",
            value: summary?.next_run_at ? formatDateTime(summary.next_run_at) : "未排期",
          },
        ]}
      />
      {dashboard.error ? <EmptyHint text={`后端不可用：${dashboard.error}`} compact /> : null}
      <CategoryStrip overview={overview.data ?? []} />
      <MapLegend
        windowKey={windowKey}
        onWindowChange={changeWindow}
        activeCategories={activeCategories}
        onToggleCategory={toggleCategory}
        untagged={geo.data?.untagged ?? 0}
      />
      <Row gutter={[12, 12]}>
        <Col xs={24} lg={16}>
          <Card size="small" variant="outlined" styles={{ body: { padding: 8 } }}>
            <WorldMap
              regions={visibleRegions}
              categories={activeCategories}
              selected={selected}
              onSelect={setSelected}
              loading={geo.loading}
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <RegionPanel
            regions={visibleRegions}
            windowKey={windowKey}
            selected={selected}
            onSelect={setSelected}
            loading={geo.loading}
          />
        </Col>
      </Row>
    </div>
  );
}
```

- [ ] **Step 2: 换路由、删旧页面**

`frontend/src/App.tsx`：把 `import DashboardPage from "./pages/DashboardPage";` 换成

```tsx
import MapBoardPage from "./pages/MapBoardPage";
```

并把 `index` 路由换成

```tsx
        <Route index element={<MapBoardPage />} />
```

然后删除旧文件：

```bash
git rm frontend/src/pages/DashboardPage.tsx
```

- [ ] **Step 3: 跑构建**

Run: `cd frontend && npm run build`
Expected: PASS（类型检查 + 产物构建；若报 `DashboardPage` 仍被引用，检查 `App.tsx` 是否漏改）

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/MapBoardPage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): 看板改为世界地图页"
```

---

## Task 16: 源管理页地区下拉

**Files:**
- Modify: `frontend/src/pages/SourcesPage.tsx`

- [ ] **Step 1: 接上地区字段**

1. `EMPTY_FORM` 增加 `region: "",`
2. `openEdit` 的 `form.setFieldsValue({...})` 增加 `region: item.region,`
3. 组件内增加地区选项数据源：

```tsx
  const regions = useAsync(() => api.regions(), []);
```

4. 在表单里「采集板块」那一项后面增加：

```tsx
          <Form.Item
            name="region"
            label="来源地区（打标失败时的兜底）"
            tooltip="只在该源的文章没能从正文识别出发生地时使用"
          >
            <Select
              allowClear
              placeholder="留空则不参与兜底"
              options={(regions.data?.items ?? []).map((item) => ({
                label: `${item.name}（${item.code}）`,
                value: item.code,
              }))}
            />
          </Form.Item>
```

5. 表格 `columns` 里增加一列：

```tsx
    { title: "地区", dataIndex: "region", width: 100, render: (value: string) => value || "—" },
```

- [ ] **Step 2: 跑构建**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 3: 手动确认文件未超 300 行**

Run: `wc -l frontend/src/pages/SourcesPage.tsx`
Expected: < 300（若超过，按 AGENTS.md 把抽屉表单抽成 `components/sources/SourceForm.tsx` 再提交）

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/SourcesPage.tsx
git commit -m "feat(frontend): 源管理支持配置来源地区"
```

---

## Task 17: 文档与全量验收

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 更新 README**

在「页面：…」那一段补上世界看板与地区词表的说明：

```markdown
页面：看板（世界地图）、政治/经济/金融/军事四个差异化板块页、源管理、任务管理；顶栏含"待确认"审核抽屉与"手动采集"按钮。

看板即世界地图：底层按国家填色表示新闻热度，上层彩色点表示各板块分布，点击地区在右栏就地查看该地区新闻，
时间窗默认近 24 小时（可切 7 / 30 天）。图上「未定位 N 条」表示该时间窗内没有地理标签的文章数。

- 地区词表在 `backend/app/core/geo.py`（国家 code + 中文名 + 别名 + 坐标，另含台海/加沙/南海/红海/北极等热点区）。
  增补国家只需在词表里加一条，再重跑一次底图脚本：
  `cd frontend && node scripts/build-world-geo.mjs /tmp/ne_110m_countries.geojson`，
  `backend/tests/test_geo_asset.py` 会检查词表里的每个国家在底图里都有几何。
- 文章地区标签由抽取管线顺带产出（不额外调用 LLM），抽取关闭或识别失败时回退到「来源地区」；
  来源地区在源管理页配置。
```

在「主要 API」列表补三行：

```markdown
- `GET /api/dashboard/geo?window=24h|7d|30d` 看板地区聚合
- `GET /api/regions` 地区选项（国家 + 热点区）
- `GET /api/regions/{code}/articles?window=&category=` 某地区文章列表
```

- [ ] **Step 2: 后端全量测试**

Run: `cd backend && uv run pytest -q`
Expected: 全部通过（含既有用例）

- [ ] **Step 3: 前端全量校验**

Run: `cd frontend && npm test && npm run build`
Expected: 单测通过、构建通过

- [ ] **Step 4: 手动验收**

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

打开 `http://localhost:5173/`，逐条确认：

- 首屏是地图，不是卡片列表
- 点采集任务跑一次后，地图上出现彩点，国家填色有深浅差异
- 点某个国家 → 右栏出现该地区新闻列表；点「← 返回地区榜」回到榜单
- 点图例里的「军事」→ 只剩军事点与被重算后的填色；再点回来恢复
- 切到「7 天」→ 地图数据刷新，右栏重置回地区榜

- [ ] **Step 5: 提交**

```bash
git add README.md
git commit -m "docs: 补充世界看板与地区词表说明"
```

---

## 完成标准

- `cd backend && uv run pytest -q` 全绿
- `cd frontend && npm test && npm run build` 全绿
- 上面「手动验收」5 条全部成立
- 新增/修改的每个前端文件 < 300 行，后端每个模块职责单一（词表 / 仓储 / 策略 / 路由分开）
