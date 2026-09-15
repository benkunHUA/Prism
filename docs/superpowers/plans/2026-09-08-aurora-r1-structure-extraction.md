# Aurora R1 实施计划（结构化数据与提取管线）

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) 或 superpowers:executing-plans（本会话子代理通道不可用时用后者）。Steps use checkbox (`- [ ]`) syntax for tracking。

**Goal:** 为四大板块落地差异化数据层：5 张新表、LLM 结构化提取（校验/归并/分级）、行情快照 Provider、板块查询与审核 API，全部经 pytest 验证。

**Architecture:** 在既有 FastAPI + SQLite(WAL) 单进程架构上扩展：ORM 新增 timeline_events / military_weapons / macro_indicators / market_snapshots / stance_topics；`services/extraction/` 承载 schema、提示词、分级与写库；`services/marketdata.py` 承载行情 Provider；API 增加 boards 查询与 moderations 审核端点。

**Tech Stack:** 沿用 Python 3.12 + FastAPI + SQLAlchemy 2 + pytest；新增无第三方依赖（JSON 提取用标准库 + pydantic）。

---

## 文件结构（新增/修改）

```
backend/app/models/entities.py          # 新增 5 个 ORM（修改）
backend/app/models/__init__.py          # 导出（修改）
backend/app/core/constants.py           # 词表/自动确认表（修改）
backend/app/core/config.py              # extract_enabled / market_symbols（修改）
backend/.env.example                    # 新增配置示例（修改）
backend/app/repositories/timeline.py    # 新增
backend/app/repositories/weapons.py     # 新增
backend/app/repositories/indicators.py  # 新增
backend/app/repositories/stances.py     # 新增
backend/app/repositories/snapshots.py   # 新增
backend/app/services/extraction/__init__.py
backend/app/services/extraction/schemas.py
backend/app/services/extraction/prompts.py
backend/app/services/extraction/risk.py
backend/app/services/extraction/extractor.py
backend/app/services/marketdata.py       # 新增
backend/app/services/flow.py             # 提取+快照接入（修改）
backend/app/api/routes_boards.py         # 新增
backend/app/api/routes_moderations.py    # 新增
backend/app/main.py                      # 注册路由（修改）
backend/tests/...                        # 对应测试新增/修改
```

---

### Task 1: 新增 5 张表的 ORM 与词表

**Files:**
- Modify: `backend/app/models/entities.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/core/constants.py`
- Test: `backend/tests/test_models.py`（追加）

- [ ] **Step 1: 追加失败测试**

```python
from app.models.entities import (
    MacroIndicator,
    MarketSnapshot,
    MilitaryWeapon,
    StanceTopic,
    TimelineEvent,
)


def test_new_domain_tables_crud(tmp_path):
    engine = _engine(tmp_path)
    factory = make_session_factory(engine)
    with factory() as db:
        ev = TimelineEvent(category="military", subtype="冲突进展", actor="双方",
                           region="俄乌", summary="s", importance="high",
                           verification_status="draft", merge_key="m1")
        wp = MilitaryWeapon(name="X", origin="US", weapon_type="导弹",
                            merge_key="w1")
        ind = MacroIndicator(indicator="CPI", region="中国", period="2026-08",
                             value=0.4, unit="%", merge_key="i1")
        sn = MarketSnapshot(asset_code="^spx", asset_name="标普500", price=5980.0,
                            batch_id="b1", source="stooq")
        st = StanceTopic(topic="对华", actor="美国商务部", stance_text="趋严",
                         verification_status="draft")
        db.add_all([ev, wp, ind, sn, st])
        db.commit()
        assert all(x.id for x in (ev, wp, ind, sn, st))
    engine.dispose()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_models.py -q`
Expected: FAIL（实体不存在）。

- [ ] **Step 3: entities.py 追加 5 个实体**

在 `AnalysisArticle` 之后、`Task` 之前插入：

```python
class TimelineEvent(Base):
    """四类事件共用底表：政治 / 军事冲突 / 经济政策 / 金融市场。"""
    __tablename__ = "timeline_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(20), index=True)
    subtype: Mapped[str] = mapped_column(String(50))
    actor: Mapped[str] = mapped_column(Text, default="")
    region: Mapped[str] = mapped_column(String(200), default="")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    importance: Mapped[str] = mapped_column(String(10), default="medium")
    verification_status: Mapped[str] = mapped_column(String(10), default="draft", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )
    group_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    merge_key: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class MilitaryWeapon(Base):
    __tablename__ = "military_weapons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    original_name: Mapped[str] = mapped_column(String(500), default="")
    origin: Mapped[str] = mapped_column(String(200), default="")
    weapon_type: Mapped[str] = mapped_column(String(100), default="")
    params_text: Mapped[str] = mapped_column(Text, default="")
    lifecycle_status: Mapped[str] = mapped_column(String(20), default="研发")
    merge_key: Mapped[str] = mapped_column(String(64), index=True)
    verification_status: Mapped[str] = mapped_column(String(10), default="draft", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class MacroIndicator(Base):
    __tablename__ = "macro_indicators"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator: Mapped[str] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(200), default="")
    period: Mapped[str] = mapped_column(String(50))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20), default="")
    previous: Mapped[float | None] = mapped_column(Float, nullable=True)
    forecast: Mapped[float | None] = mapped_column(Float, nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    merge_key: Mapped[str] = mapped_column(String(64), index=True)
    verification_status: Mapped[str] = mapped_column(String(10), default="confirmed", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_code: Mapped[str] = mapped_column(String(50), index=True)
    asset_name: Mapped[str] = mapped_column(String(100), default="")
    asset_class: Mapped[str] = mapped_column(String(20), default="index")
    price: Mapped[float] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(100), default="stooq")


class StanceTopic(Base):
    __tablename__ = "stance_topics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String(100), index=True)
    actor: Mapped[str] = mapped_column(String(200), index=True)
    stance_text: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(String(50), default="中性")
    stated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(10), default="draft", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
```

同步修改 `entities.py` 顶部 import：在 `from sqlalchemy import ...` 中加入 `Float`；`AnalysisArticle` 之后的 `Article.analysis_links` 等引用不受影响。

- [ ] **Step 4: models/__init__.py 追加导出**

```python
from app.models.entities import (  # noqa: F401
    MacroIndicator,
    MarketSnapshot,
    MilitaryWeapon,
    StanceTopic,
    TimelineEvent,
)
```

- [ ] **Step 5: constants.py 增加词表与自动确认类型**

```python
TIMELINE_SUBTYPES = {
    "politics": ["选举/组阁", "立法与投票", "外交与峰会", "制裁与出口管制", "条约与协议", "安全战略声明"],
    "military": ["冲突进展", "停火与和谈", "军事行动", "袭击与损失"],
    "economy": ["货币政策", "财政政策", "贸易政策", "产业政策", "监管与改革"],
    "finance": ["市场异动", "融资/IPO/并购", "监管动态", "公司重大事件", "资金与流动性"],
}
WEAPON_LIFECYCLE = ["研发", "测试", "列装", "部署", "出口", "退役"]
STANCE_TOPICS = ["对华", "俄乌", "中东", "台海", "贸易", "科技管制", "气候", "能源"]
STANCE_TONES = ["趋严", "缓和", "支持", "反对", "中性", "未定"]
IMPORTANCE_LEVELS = ["high", "medium", "low"]
```

- [ ] **Step 6: 运行通过**

Run: `cd backend && uv run pytest tests/test_models.py -q`
Expected: 3 passed。

- [ ] **Step 7: 提交**

```bash
git add backend/app/models backend/app/core/constants.py backend/tests/test_models.py
git commit -m "feat(backend): 差异化结构化表 ORM"
```

---

### Task 2: 配置字段 + 五个仓储

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/tests/test_config.py`
- Create: `backend/app/repositories/timeline.py`
- Create: `backend/app/repositories/weapons.py`
- Create: `backend/app/repositories/indicators.py`
- Create: `backend/app/repositories/stances.py`
- Create: `backend/app/repositories/snapshots.py`
- Test: `backend/tests/test_domain_repos.py`

- [ ] **Step 1: Settings 增加 extract_enabled 与 market_symbols**

在 `config.py` 的 `top_articles_per_analysis: int = 30` 之后增加：

```python
    extract_enabled: bool = True
    market_symbols: str = ""  # 例："标普500=^spx,美债10Y=10usy.b"
```

`.env.example` 增加：

```dotenv
# 结构化提取与行情
EXTRACT_ENABLED=true
MARKET_SYMBOLS=
```

`test_config.py::test_defaults` 追加断言：

```python
    assert s.extract_enabled is True
    assert s.market_symbols == ""
```

- [ ] **Step 2: 写仓储失败测试（新增文件 test_domain_repos.py）**

```python
from app.models.entities import Category
from app.repositories import indicators, snapshots, stances, timeline, weapons
from app.repositories import sources


def _article(db):
    src = sources.create_source(db, name="S", url="https://example.com/rss",
                                feed_type="rss", lang="en", categories=[Category.politics.value])
    from app.repositories import articles

    articles.insert_articles(db, [dict(source_id=src.id, category="politics",
                                       url="https://example.com/a", title="A", summary="s",
                                       content_text="", published_at=None, lang="en",
                                       dedupe_hash="ha")])
    return articles.list_articles(db, category="politics")[0]


def test_timeline_upsert_and_list(db):
    row, created = timeline.upsert_event(
        db, category="politics", subtype="立法与投票", actor="欧盟议会",
        region="欧盟", summary="修正案通过", importance="medium",
        verification_status="confirmed", article_id=None, group_key=None,
        merge_key="mk1",
    )
    assert created is True and row.verification_status == "confirmed"
    row2, created2 = timeline.upsert_event(
        db, category="politics", subtype="立法与投票", actor="欧盟议会",
        region="欧盟", summary="修正案二读通过", importance="high",
        verification_status="confirmed", article_id=None, group_key=None,
        merge_key="mk1",
    )
    assert created2 is False and row2.id == row.id
    assert row2.summary == "修正案二读通过"
    assert len(timeline.list_events(db, category="politics")) == 1


def test_weapon_upsert_updates_not_duplicates(db):
    w1, c1 = weapons.upsert_weapon(db, name="X", original_name="", origin="US",
                                   weapon_type="导弹", params_text="v1",
                                   lifecycle_status="研发", merge_key="w1",
                                   verification_status="draft", article_id=None)
    assert c1 is True
    w2, c2 = weapons.upsert_weapon(db, name="X", original_name="", origin="US",
                                   weapon_type="导弹", params_text="v2 新增射程",
                                   lifecycle_status="测试", merge_key="w1",
                                   verification_status="draft", article_id=None)
    assert c2 is False and w2.id == w1.id
    assert w2.params_text == "v2 新增射程" and w2.lifecycle_status == "测试"
    assert len(weapons.list_weapons(db)) == 1


def test_indicator_correction_overwrites(db):
    i1, c1 = indicators.upsert_indicator(db, indicator="CPI", region="中国",
                                         period="2026-08", value=0.4, unit="%",
                                         previous=0.5, forecast=0.6, merge_key="i1",
                                         article_id=None)
    assert c1 is True
    indicators.upsert_indicator(db, indicator="CPI", region="中国", period="2026-08",
                                value=0.3, unit="%", previous=0.5, forecast=0.6,
                                merge_key="i1", article_id=None)
    assert indicators.list_indicators(db, indicator="CPI", region="中国")[0].value == 0.3


def test_stance_appends_history(db):
    stances.create_stance(db, topic="对华", actor="美国商务部", stance_text="名单扩大",
                          tone="趋严", verification_status="draft", article_id=None)
    stances.create_stance(db, topic="对华", actor="美国商务部", stance_text="进一步扩大",
                          tone="趋严", verification_status="confirmed", article_id=None)
    rows = stances.list_stances(db, topic="对华", actor="美国商务部")
    assert len(rows) == 2
    assert rows[0].stance_text == "进一步扩大"


def test_snapshot_batch(db):
    snapshots.insert_snapshots(db, [
        dict(asset_code="^spx", asset_name="标普500", asset_class="index",
             price=5980.0, change_pct=-0.8, batch_id="b1", source="stooq"),
        dict(asset_code="xau", asset_name="黄金", asset_class="commodity",
             price=2610.0, change_pct=0.6, batch_id="b1", source="stooq"),
    ])
    snapshots.insert_snapshots(db, [
        dict(asset_code="^spx", asset_name="标普500", asset_class="index",
             price=5990.0, change_pct=0.2, batch_id="b2", source="stooq"),
    ])
    assert snapshots.latest_batch_id(db) == "b2"
    assert len(snapshots.list_snapshots(db, batch_id="b1")) == 2
    assert len(snapshots.list_snapshots(db)) == 3
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_domain_repos.py -q`
Expected: FAIL。

- [ ] **Step 4: 实现五个仓储**

```python
# backend/app/repositories/timeline.py
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import TimelineEvent, utcnow


def get_event(db: Session, event_id: int) -> TimelineEvent | None:
    return db.get(TimelineEvent, event_id)


def upsert_event(db: Session, *, category: str, subtype: str, actor: str = "",
                 region: str = "", occurred_at: datetime | None = None,
                 summary: str = "", importance: str = "medium",
                 verification_status: str = "draft", confidence: float = 0.5,
                 article_id: int | None = None, group_key: str | None = None,
                 merge_key: str) -> tuple[TimelineEvent, bool]:
    row = db.query(TimelineEvent).filter(TimelineEvent.merge_key == merge_key).first()
    if row is None:
        row = TimelineEvent(category=category, subtype=subtype, merge_key=merge_key)
        db.add(row)
        created = True
    else:
        created = False
    row.category = category
    row.subtype = subtype
    row.actor = actor
    row.region = region
    if occurred_at:
        row.occurred_at = max(row.occurred_at, occurred_at) if row.occurred_at else occurred_at
    if summary:
        row.summary = summary
    row.importance = importance
    row.confidence = confidence
    if row.verification_status != "confirmed" and verification_status == "confirmed":
        row.verification_status = "confirmed"
    if group_key:
        row.group_key = group_key
    if article_id:
        row.article_id = article_id
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row, created


def list_events(db: Session, category: str | None = None,
                subtype: str | None = None, verification: str | None = None,
                limit: int = 100) -> list[TimelineEvent]:
    query = db.query(TimelineEvent)
    if category:
        query = query.filter(TimelineEvent.category == category)
    if subtype:
        query = query.filter(TimelineEvent.subtype == subtype)
    if verification:
        query = query.filter(TimelineEvent.verification_status == verification)
    return query.order_by(TimelineEvent.occurred_at.desc().nullslast(),
                          TimelineEvent.updated_at.desc()).limit(limit).all()


def update_event(db: Session, row: TimelineEvent, *, summary: str | None = None,
                 actor: str | None = None, region: str | None = None,
                 importance: str | None = None,
                 verification_status: str | None = None) -> TimelineEvent:
    if summary is not None:
        row.summary = summary
    if actor is not None:
        row.actor = actor
    if region is not None:
        row.region = region
    if importance is not None:
        row.importance = importance
    if verification_status is not None:
        row.verification_status = verification_status
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row
```

```python
# backend/app/repositories/weapons.py
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import MilitaryWeapon, utcnow


def get_weapon(db: Session, weapon_id: int) -> MilitaryWeapon | None:
    return db.get(MilitaryWeapon, weapon_id)


def upsert_weapon(db: Session, *, name: str, original_name: str = "", origin: str = "",
                  weapon_type: str = "", params_text: str = "",
                  lifecycle_status: str = "研发", merge_key: str,
                  verification_status: str = "draft", confidence: float = 0.5,
                  article_id: int | None = None,
                  first_seen_at: datetime | None = None) -> tuple[MilitaryWeapon, bool]:
    row = db.query(MilitaryWeapon).filter(MilitaryWeapon.merge_key == merge_key).first()
    now = utcnow()
    if row is None:
        row = MilitaryWeapon(merge_key=merge_key, first_seen_at=first_seen_at or now)
        db.add(row)
        created = True
    else:
        created = False
    row.name = name
    row.original_name = original_name
    row.origin = origin
    row.weapon_type = weapon_type
    if params_text:
        row.params_text = params_text
    if lifecycle_status:
        row.lifecycle_status = lifecycle_status
    row.confidence = confidence
    if row.verification_status != "confirmed" and verification_status == "confirmed":
        row.verification_status = "confirmed"
    if article_id:
        row.article_id = article_id
    row.last_seen_at = now
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return row, created


def list_weapons(db: Session, lifecycle: str | None = None,
                 verification: str | None = None,
                 limit: int = 100) -> list[MilitaryWeapon]:
    query = db.query(MilitaryWeapon)
    if lifecycle:
        query = query.filter(MilitaryWeapon.lifecycle_status == lifecycle)
    if verification:
        query = query.filter(MilitaryWeapon.verification_status == verification)
    return query.order_by(MilitaryWeapon.updated_at.desc()).limit(limit).all()


def update_weapon(db: Session, row: MilitaryWeapon, *, name: str | None = None,
                  origin: str | None = None, weapon_type: str | None = None,
                  params_text: str | None = None,
                  lifecycle_status: str | None = None,
                  verification_status: str | None = None) -> MilitaryWeapon:
    for field, value in (("name", name), ("origin", origin), ("weapon_type", weapon_type),
                         ("params_text", params_text),
                         ("lifecycle_status", lifecycle_status),
                         ("verification_status", verification_status)):
        if value is not None:
            setattr(row, field, value)
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row
```

```python
# backend/app/repositories/indicators.py
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import MacroIndicator, utcnow


def get_indicator(db: Session, indicator_id: int) -> MacroIndicator | None:
    return db.get(MacroIndicator, indicator_id)


def upsert_indicator(db: Session, *, indicator: str, region: str, period: str,
                     value: float, unit: str = "", previous: float | None = None,
                     forecast: float | None = None,
                     released_at: datetime | None = None, merge_key: str,
                     verification_status: str = "confirmed",
                     confidence: float = 0.8,
                     article_id: int | None = None) -> tuple[MacroIndicator, bool]:
    row = db.query(MacroIndicator).filter(MacroIndicator.merge_key == merge_key).first()
    if row is None:
        row = MacroIndicator(merge_key=merge_key)
        db.add(row)
        created = True
    else:
        created = False
    row.indicator = indicator
    row.region = region
    row.period = period
    row.value = value
    row.unit = unit
    if previous is not None:
        row.previous = previous
    if forecast is not None:
        row.forecast = forecast
    if released_at:
        row.released_at = released_at
    row.verification_status = verification_status
    row.confidence = confidence
    if article_id:
        row.article_id = article_id
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row, created


def list_indicators(db: Session, indicator: str | None = None,
                    region: str | None = None, limit: int = 100) -> list[MacroIndicator]:
    query = db.query(MacroIndicator)
    if indicator:
        query = query.filter(MacroIndicator.indicator == indicator)
    if region:
        query = query.filter(MacroIndicator.region == region)
    return query.order_by(MacroIndicator.released_at.desc().nullslast(),
                          MacroIndicator.updated_at.desc()).limit(limit).all()


def update_indicator(db: Session, row: MacroIndicator, *,
                     value: float | None = None, previous: float | None = None,
                     forecast: float | None = None,
                     verification_status: str | None = None) -> MacroIndicator:
    if value is not None:
        row.value = value
    if previous is not None:
        row.previous = previous
    if forecast is not None:
        row.forecast = forecast
    if verification_status is not None:
        row.verification_status = verification_status
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row
```

```python
# backend/app/repositories/stances.py
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import StanceTopic


def create_stance(db: Session, *, topic: str, actor: str, stance_text: str,
                  tone: str = "中性", stated_at: datetime | None = None,
                  verification_status: str = "draft", confidence: float = 0.5,
                  article_id: int | None = None) -> StanceTopic:
    row = StanceTopic(topic=topic, actor=actor, stance_text=stance_text, tone=tone,
                      stated_at=stated_at, verification_status=verification_status,
                      confidence=confidence, article_id=article_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_stances(db: Session, topic: str | None = None, actor: str | None = None,
                 verification: str | None = None,
                 limit: int = 200) -> list[StanceTopic]:
    query = db.query(StanceTopic)
    if topic:
        query = query.filter(StanceTopic.topic == topic)
    if actor:
        query = query.filter(StanceTopic.actor == actor)
    if verification:
        query = query.filter(StanceTopic.verification_status == verification)
    return query.order_by(StanceTopic.stated_at.desc().nullslast(),
                          StanceTopic.created_at.desc()).limit(limit).all()


def update_stance(db: Session, row: StanceTopic, *, stance_text: str | None = None,
                  tone: str | None = None,
                  verification_status: str | None = None) -> StanceTopic:
    if stance_text is not None:
        row.stance_text = stance_text
    if tone is not None:
        row.tone = tone
    if verification_status is not None:
        row.verification_status = verification_status
    db.commit()
    db.refresh(row)
    return row
```

```python
# backend/app/repositories/snapshots.py
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import MarketSnapshot


def insert_snapshots(db: Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    db.add_all([MarketSnapshot(**row) for row in rows])
    db.commit()
    return len(rows)


def latest_batch_id(db: Session) -> str | None:
    row = db.query(MarketSnapshot).order_by(MarketSnapshot.captured_at.desc()).first()
    return row.batch_id if row else None


def list_snapshots(db: Session, batch_id: str | None = None,
                   asset_class: str | None = None,
                   limit: int = 200) -> list[MarketSnapshot]:
    query = db.query(MarketSnapshot)
    if batch_id:
        query = query.filter(MarketSnapshot.batch_id == batch_id)
    if asset_class:
        query = query.filter(MarketSnapshot.asset_class == asset_class)
    return query.order_by(MarketSnapshot.captured_at.desc(), MarketSnapshot.asset_code).limit(limit).all()
```

- [ ] **Step 5: 运行通过**

Run: `cd backend && uv run pytest tests/test_config.py tests/test_domain_repos.py -q`
Expected: 1 个既有 config 用例（新增断言）+ 5 个仓储用例 = 6 passed。

- [ ] **Step 6: 提交**

```bash
git add backend/app/core/config.py backend/.env.example backend/tests/test_config.py
git add backend/app/repositories/timeline.py backend/app/repositories/weapons.py
git add backend/app/repositories/indicators.py backend/app/repositories/stances.py
git add backend/app/repositories/snapshots.py backend/tests/test_domain_repos.py
git commit -m "feat(backend): 差异化领域仓储与配置"
```

---

### Task 3: 提取 Schema、提示词与分级规则

**Files:**
- Create: `backend/app/services/extraction/__init__.py`
- Create: `backend/app/services/extraction/schemas.py`
- Create: `backend/app/services/extraction/prompts.py`
- Create: `backend/app/services/extraction/risk.py`
- Test: `backend/tests/test_extraction_rules.py`

- [ ] **Step 1: 写失败测试**

```python
from app.services.extraction.prompts import build_extraction_prompt
from app.services.extraction.risk import event_auto_verification
from app.services.extraction.schemas import (
    MilitaryExtraction,
    PoliticsExtraction,
)


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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_extraction_rules.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现四个文件**

```python
# backend/app/services/extraction/schemas.py
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import (
    IMPORTANCE_LEVELS,
    STANCE_TONES,
    TIMELINE_SUBTYPES,
    WEAPON_LIFECYCLE,
)


class TimelineItemIn(BaseModel):
    subtype: str
    actor: str = ""
    region: str = ""
    occurred_at: datetime | None = None
    summary: str = ""
    importance: str = Field(default="medium")
    group_key: str | None = None


class WeaponItemIn(BaseModel):
    name: str = Field(min_length=1)
    original_name: str = ""
    origin: str = ""
    weapon_type: str = ""
    params_text: str = ""
    lifecycle_status: str = Field(default="研发")
    first_seen_at: datetime | None = None


class IndicatorItemIn(BaseModel):
    indicator: str
    region: str = ""
    period: str
    value: float
    unit: str = ""
    previous: float | None = None
    forecast: float | None = None
    released_at: datetime | None = None


class StanceItemIn(BaseModel):
    topic: str
    actor: str
    stance_text: str
    tone: str = "中性"
    stated_at: datetime | None = None


class PoliticsExtraction(BaseModel):
    events: list[TimelineItemIn] = []
    stances: list[StanceItemIn] = []


class MilitaryExtraction(BaseModel):
    weapons: list[WeaponItemIn] = []
    conflicts: list[TimelineItemIn] = []


class EconomyExtraction(BaseModel):
    indicators: list[IndicatorItemIn] = []
    policies: list[TimelineItemIn] = []


class FinanceExtraction(BaseModel):
    events: list[TimelineItemIn] = []


CATEGORY_MODEL = {
    "politics": PoliticsExtraction,
    "military": MilitaryExtraction,
    "economy": EconomyExtraction,
    "finance": FinanceExtraction,
}
```

```python
# backend/app/services/extraction/prompts.py
from app.core.constants import STANCE_TOPICS, TIMELINE_SUBTYPES, WEAPON_LIFECYCLE


def build_extraction_prompt(category: str, *, title: str, body: str, url: str) -> str:
    allowed = TIMELINE_SUBTYPES.get(category, [])
    extra = ""
    if category == "politics":
        extra = (
            "stances 数组（可空）：topic 取自 " + "、".join(STANCE_TOPICS)
            + "；actor 为表态机构；stance_text 简述立场要点；tone 取 趋严/缓和/支持/反对/中性/未定。"
        )
    elif category == "military":
        extra = "weapons 数组（可空）：name 名称、origin 国别、weapon_type 类型（战斗机/舰艇/导弹/无人机/坦克/雷达等）、params_text 参数要点、lifecycle_status 取自 " + "、".join(WEAPON_LIFECYCLE) + "。"
    elif category == "economy":
        extra = "indicators 数组（可空）：indicator 指标名、region 地区、period 周期（如 2026-08）、value 数值、unit 单位、previous/forecast 前值与预期（可空）、released_at 发布时间。"
    return (
        f"你是 {category} 板块的结构化信息提取器。仅基于给定文章，输出 JSON，不要输出其它文字。\n"
        f"events 数组（可空）：subtype 取自 " + "、".join(allowed)
        + "；actor 主体；region 地区；occurred_at ISO 时间；summary 事实摘要（不改写、不推断）；"
        "importance 取 high/medium/low；同一战线/同一事件多次报道时给相同 group_key。\n"
        + extra
        + "\n文章标题：" + title
        + "\n原文链接：" + url
        + "\n正文：\n" + (body or "")[:4000]
    )
```

```python
# backend/app/services/extraction/risk.py
AUTO_TIMELINE_SUBTYPES = {
    ("politics", "选举/组阁"),
    ("politics", "立法与投票"),
    ("military", "停火与和谈"),
    ("economy", "货币政策"),
    ("economy", "财政政策"),
    ("finance", "融资/IPO/并购"),
}
DECISION_WORDS = ("结果", "通过", "胜出", "宣布", "决定", "签署", "正式")
SPECIAL_WORDS = {
    ("politics", "选举/组阁"): ("结果", "胜出", "就职", "正式成立"),
    ("politics", "立法与投票"): ("通过", "否决", "表决"),
    ("military", "停火与和谈"): ("停火", "协议", "达成", "宣布"),
    ("economy", "货币政策"): ("利率", "决定", "维持", "上调", "下调"),
    ("economy", "财政政策"): ("预算", "通过", "宣布", "方案"),
    ("finance", "融资/IPO/并购"): ("收购", "合并", "IPO", "上市", "发行", "回购"),
}


def event_auto_verification(category: str, subtype: str, summary: str) -> str:
    """返回 confirmed 或 draft。"""
    if (category, subtype) not in AUTO_TIMELINE_SUBTYPES:
        return "draft"
    words = SPECIAL_WORDS.get((category, subtype), DECISION_WORDS)
    return "confirmed" if any(w in summary for w in words) else "draft"
```

- [ ] **Step 4: 运行通过**

Run: `cd backend && uv run pytest tests/test_extraction_rules.py -q`
Expected: 4 passed。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/extraction backend/tests/test_extraction_rules.py
git commit -m "feat(backend): 提取 schema 与分级规则"
```

---

### Task 4: 结构化提取器（解析 → 归并 → 写库）

**Files:**
- Create: `backend/app/services/extraction/extractor.py`
- Test: `backend/tests/test_extractor.py`

- [ ] **Step 1: 写失败测试**

```python
import json

from app.models.entities import Category, Source
from app.repositories import articles, indicators, sources, stances, timeline, weapons
from app.services.extraction.extractor import extract_article
from app.services.llm import ChatProvider


class FakeProvider(ChatProvider):
    name = "fake"

    def __init__(self, settings, payload_by_category):
        super().__init__(settings)
        self.payload_by_category = payload_by_category

    def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
        category = self.payload_by_category["category"]
        return json.dumps(self.payload_by_category[category], ensure_ascii=False)


def _make_article(db, category, url):
    src = sources.create_source(db, name="S", url=f"https://example.com/{category}",
                                feed_type="rss", lang="en", categories=[category])
    from datetime import datetime, timezone

    articles.insert_articles(db, [dict(source_id=src.id, category=category, url=url,
                                       title=f"T-{category}", summary="s", content_text="正文",
                                       published_at=datetime.now(timezone.utc).replace(tzinfo=None),
                                       lang="en", dedupe_hash=f"h-{category}")])
    return articles.list_articles(db, category=category)[0]


def test_extract_politics_writes_events_and_stances(db):
    from app.core.config import Settings

    art = _make_article(db, "politics", "https://example.com/p1")
    provider = FakeProvider(Settings(_env_file=None), {
        "category": "politics",
        "politics": {
            "events": [{"subtype": "立法与投票", "actor": "欧盟议会", "region": "欧盟",
                        "occurred_at": "2026-09-08T09:00:00", "summary": "修正案表决通过",
                        "importance": "high"}],
            "stances": [{"topic": "对华", "actor": "美国商务部", "stance_text": "名单扩大",
                         "tone": "趋严", "stated_at": "2026-09-08T08:00:00"}],
        },
    })
    stats = extract_article(db, art, provider, Settings(_env_file=None))
    assert stats["created"] == 2
    events = timeline.list_events(db, category="politics")
    assert events[0].verification_status == "confirmed"  # 表决通过 → 自动确认
    assert stances.list_stances(db)[0].verification_status == "draft"


def test_extract_military_writes_draft_weapon(db):
    from app.core.config import Settings

    art = _make_article(db, "military", "https://example.com/m1")
    provider = FakeProvider(Settings(_env_file=None), {
        "category": "military",
        "military": {
            "weapons": [{"name": "第六代验证机", "origin": "美国", "weapon_type": "战斗机",
                         "params_text": "飞翼布局", "lifecycle_status": "研发"}],
            "conflicts": [{"subtype": "冲突进展", "actor": "乌军", "region": "俄乌",
                           "occurred_at": "2026-09-08T06:00:00", "summary": "击退多方向进攻",
                           "importance": "high"}],
        },
    })
    extract_article(db, art, provider, Settings(_env_file=None))
    assert weapons.list_weapons(db)[0].verification_status == "draft"
    assert timeline.list_events(db, category="military")[0].verification_status == "draft"


def test_extract_economy_writes_confirmed_indicator(db):
    from app.core.config import Settings

    art = _make_article(db, "economy", "https://example.com/e1")
    provider = FakeProvider(Settings(_env_file=None), {
        "category": "economy",
        "economy": {
            "indicators": [{"indicator": "CPI", "region": "中国", "period": "2026-08",
                            "value": 0.4, "unit": "%", "previous": 0.5, "forecast": 0.6,
                            "released_at": "2026-09-08T09:30:00"}],
            "policies": [],
        },
    })
    extract_article(db, art, provider, Settings(_env_file=None))
    assert indicators.list_indicators(db)[0].verification_status == "confirmed"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_extractor.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现 extractor.py**

```python
from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import Article
from app.repositories import indicators as indicators_repo
from app.repositories import stances as stances_repo
from app.repositories import timeline as timeline_repo
from app.repositories import weapons as weapons_repo
from app.services.extraction.prompts import build_extraction_prompt
from app.services.extraction.risk import event_auto_verification
from app.services.extraction.schemas import CATEGORY_MODEL, TimelineItemIn, WeaponItemIn
from app.services.llm import ChatProvider
from app.services.urlutil import normalize_title


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _timeline_merge_key(category: str, item: TimelineItemIn) -> str:
    if item.group_key:
        raw = f"{category}|{item.group_key}"
    else:
        date = item.occurred_at.date().isoformat() if item.occurred_at else "no-date"
        raw = f"{category}|{item.subtype}|{item.actor}|{item.region}|{date}|{normalize_title(item.summary[:80])}"
    return _sha(raw)


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    return json.loads(text)


def _write_timeline(db: Session, category: str, items: list[TimelineItemIn],
                    article_id: int | None, stats: dict) -> None:
    for item in items:
        verification = event_auto_verification(category, item.subtype, item.summary)
        row, created = timeline_repo.upsert_event(
            db, category=category, subtype=item.subtype, actor=item.actor,
            region=item.region, occurred_at=item.occurred_at, summary=item.summary,
            importance=item.importance, verification_status=verification,
            article_id=article_id, group_key=item.group_key,
            merge_key=_timeline_merge_key(category, item),
        )
        stats["created" if created else "updated"] += 1


def _write_weapons(db: Session, items: list[WeaponItemIn], article_id: int | None,
                   stats: dict) -> None:
    for item in items:
        merge_key = _sha(normalize_title(item.name) + "|" + normalize_title(item.origin))
        _, created = weapons_repo.upsert_weapon(
            db, name=item.name, original_name=item.original_name, origin=item.origin,
            weapon_type=item.weapon_type, params_text=item.params_text,
            lifecycle_status=item.lifecycle_status, merge_key=merge_key,
            verification_status="draft", article_id=article_id,
            first_seen_at=item.first_seen_at,
        )
        stats["created" if created else "updated"] += 1


def _article_categories(article: Article) -> list[str]:
    if article.source and article.source.source_categories:
        return [sc.category for sc in article.source.source_categories]
    return [article.category]


def extract_article(db: Session, article: Article, provider: ChatProvider,
                    settings: Settings) -> dict:
    """对单篇文章按所属板块提取并写库，返回统计。"""
    stats = {"created": 0, "updated": 0, "failed": 0}
    for category in _article_categories(article):
        model_cls = CATEGORY_MODEL.get(category)
        if model_cls is None:
            continue
        prompt = build_extraction_prompt(
            category, title=article.title, body=article.summary or article.content_text,
            url=article.url,
        )
        try:
            raw = provider.complete([{"role": "user", "content": prompt}],
                                    temperature=0.0, max_tokens=2500)
            payload = _parse_json(raw)
            parsed = model_cls.model_validate(payload)
        except Exception:  # noqa: BLE001
            stats["failed"] += 1
            continue
        if category == "politics":
            _write_timeline(db, "politics", parsed.events, article.id, stats)
            for stance in parsed.stances:
                stances_repo.create_stance(
                    db, topic=stance.topic, actor=stance.actor,
                    stance_text=stance.stance_text, tone=stance.tone,
                    stated_at=stance.stated_at, verification_status="draft",
                    article_id=article.id,
                )
                stats["created"] += 1
        elif category == "military":
            _write_timeline(db, "military", parsed.conflicts, article.id, stats)
            _write_weapons(db, parsed.weapons, article.id, stats)
        elif category == "economy":
            _write_timeline(db, "economy", parsed.policies, article.id, stats)
            for item in parsed.indicators:
                merge_key = _sha(normalize_title(item.indicator) + "|"
                                 + normalize_title(item.region) + "|" + item.period)
                indicators_repo.upsert_indicator(
                    db, indicator=item.indicator, region=item.region, period=item.period,
                    value=item.value, unit=item.unit, previous=item.previous,
                    forecast=item.forecast, released_at=item.released_at,
                    merge_key=merge_key, verification_status="confirmed",
                    article_id=article.id,
                )
                stats["created"] += 1
        elif category == "finance":
            _write_timeline(db, "finance", parsed.events, article.id, stats)
    return stats
```

- [ ] **Step 4: 运行通过**

Run: `cd backend && uv run pytest tests/test_extractor.py -q`
Expected: 3 passed。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/extraction/extractor.py backend/tests/test_extractor.py
git commit -m "feat(backend): 结构化提取器"
```

---

### Task 5: 行情快照 Provider

**Files:**
- Create: `backend/app/services/marketdata.py`
- Create: `backend/tests/data/stooq_fixture.csv`
- Test: `backend/tests/test_marketdata.py`

- [ ] **Step 1: 创建 fixture CSV**

```csv
Symbol,Date,Time,Open,High,Low,Close,Volume
^spx,2026-09-08,16:00:00,6000,6010,5950,5980,2000000000
10usy.b,2026-09-08,16:00:00,3.85,3.88,3.84,3.86,0
```

- [ ] **Step 2: 写失败测试**

```python
import httpx
from pathlib import Path

from app.core.config import Settings
from app.services.marketdata import StooqCsvProvider, run_snapshots

FIXTURE = Path(__file__).parent / "data" / "stooq_fixture.csv"


def _client_for_csv():
    content = FIXTURE.read_bytes()

    def handler(request):
        if "^spx" in str(request.url):
            return httpx.Response(200, content=content)
        raise httpx.ConnectError("boom", request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_stooq_provider_parses_csv():
    provider = StooqCsvProvider()
    rows = provider.fetch(_client_for_csv(), ["标普500=^spx"])
    assert rows[0]["asset_code"] == "^spx"
    assert rows[0]["price"] == 5980.0


def test_run_snapshots_inserts_batch_and_degrades(db):
    settings = Settings(_env_file=None, market_symbols="index|标普500=^spx,rate|美债10Y=10usy.b")
    result = run_snapshots(db, settings, client=_client_for_csv())
    assert result["fetched"] == 1
    assert len(result["errors"]) == 1
    from app.repositories import snapshots

    assert snapshots.latest_batch_id(db) is not None
    assert snapshots.list_snapshots(db)[0].price == 5980.0
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_marketdata.py -q`
Expected: FAIL。

- [ ] **Step 4: 实现 marketdata.py**

```python
from __future__ import annotations

import csv
import io
import uuid

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories import snapshots as snapshots_repo

STOOQ_URL = "https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"


class StooqCsvProvider:
    """免费行情 CSV 源；单资产失败抛 httpx.HTTPError，由调用方降级。"""

    name = "stooq"

    def fetch(self, client: httpx.Client, specs: list[str]) -> list[dict]:
        rows = []
        for spec in specs:
            asset_class, name, code = self._parse_spec(spec)
            resp = client.get(STOOQ_URL.format(symbol=code), timeout=15.0)
            resp.raise_for_status()
            text = resp.text
            reader = csv.DictReader(io.StringIO(text))
            data = next(reader, None)
            if data is None:
                raise RuntimeError(f"{code} 无数据")
            rows.append(
                {
                    "asset_code": code,
                    "asset_name": name,
                    "asset_class": asset_class,
                    "price": float(data["Close"]),
                    "change_pct": None,
                    "source": self.name,
                }
            )
        return rows

    @staticmethod
    def _parse_spec(spec: str) -> tuple[str, str, str]:
        # 形如 "index|标普500=^spx" 或 "标普500=^spx"（默认 index）
        head, _, code = spec.partition("=")
        code = code.strip()
        if "|" in head:
            asset_class, name = head.split("|", 1)
        else:
            asset_class, name = "index", head
        return asset_class.strip(), name.strip(), code


def _parse_symbols(raw: str) -> list[str]:
    return [s.strip() for s in raw.split(",") if s.strip()]


def run_snapshots(db: Session, settings: Settings, *,
                  client: httpx.Client | None = None) -> dict:
    symbols = _parse_symbols(settings.market_symbols)
    if not symbols:
        return {"fetched": 0, "errors": []}
    own = client is None
    client = client or httpx.Client(timeout=15.0)
    batch_id = uuid.uuid4().hex[:12]
    try:
        rows = []
        errors = []
        for spec in symbols:
            try:
                rows.extend(StooqCsvProvider().fetch(client, [spec]))
            except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                errors.append(f"{spec}: {type(exc).__name__}: {exc}")
        for row in rows:
            row["batch_id"] = batch_id
        snapshots_repo.insert_snapshots(db, rows)
        return {"fetched": len(rows), "errors": errors}
    finally:
        if own:
            client.close()
```

- [ ] **Step 5: 运行通过**

Run: `cd backend && uv run pytest tests/test_marketdata.py -q`
Expected: 2 passed。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/marketdata.py backend/tests/data/stooq_fixture.csv backend/tests/test_marketdata.py
git commit -m "feat(backend): 行情快照 Provider"
```

---

### Task 6: flow 接入结构化提取与行情快照

**Files:**
- Modify: `backend/app/repositories/articles.py`（增加 list_new_since）
- Modify: `backend/app/services/flow.py`
- Modify: `backend/tests/test_flow.py`

- [ ] **Step 1: articles.py 追加查询**

```python
def list_new_since(db: Session, since: datetime) -> list[Article]:
    return db.query(Article).filter(Article.fetched_at >= since).order_by(Article.id).all()
```

- [ ] **Step 2: 更新既有 flow 测试的 settings**

`tests/test_flow.py` 中三处 `Settings(_env_file=None)` 改为：

```python
Settings(_env_file=None, extract_enabled=False)
```

原因：既有 FakeProvider 返回快讯文本而非 JSON，旧用例只测采集/分析流程，不触发提取。

- [ ] **Step 3: 追加提取+行情集成测试**

```python
import json
from pathlib import Path

import httpx

from app.models.entities import Category
from app.repositories import indicators, logs, snapshots, sources, tasks
from app.services.flow import run_task_flow
from app.services.llm import ChatProvider


class JsonProvider(ChatProvider):
    name = "json"

    def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
        content = messages[-1]["content"]
        if "你是 economy" in content:
            payload = {"indicators": [], "policies": []}
        else:
            payload = {"events": []}
        return json.dumps(payload, ensure_ascii=False)


def _dual_client(stooq_csv: Path):
    feed = FIXTURE.read_bytes()
    csv_bytes = stooq_csv.read_bytes()

    def handler(request):
        if "stooq.com" in str(request.url):
            return httpx.Response(200, content=csv_bytes)
        return httpx.Response(200, content=feed)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_collect_flow_runs_extraction_and_snapshots(db, tmp_path):
    from app.core.config import Settings

    src = sources.create_source(
        db, name="Fixture", url="https://example.com/rss", feed_type="rss", lang="en",
        categories=[Category.economy.value, Category.finance.value],
    )
    task = tasks.create_task(db, name="采集", kind="collect", category=None, cron="0 */4 * * *")
    settings = Settings(
        _env_file=None, extract_enabled=True,
        market_symbols="index|标普500=^spx",
    )
    stooq = tmp_path / "stooq.csv"
    stooq.write_text("Symbol,Date,Time,Open,High,Low,Close,Volume\n"
                     "^spx,2026-09-08,16:00:00,6000,6010,5950,5980,1\n")
    result = run_task_flow(
        db, task, client=_dual_client(stooq), provider=JsonProvider(settings), settings=settings,
    )
    assert result["status"] == "success"
    assert result["new"] == 2
    assert logs.list_logs(db)[0].status == "success"
    assert snapshots.latest_batch_id(db) is not None
    assert len(indicators.list_indicators(db)) == 0  # fixture 正文无指标，提取返回空
```

说明：提取正确性由 Task 4 的单测覆盖，此处只验证 flow 的调用与日志集成。

- [ ] **Step 4: 修改 flow.py**

在 `run_task_flow` 的 collect 分支中，采集入库之后、生成快讯之前插入提取与行情：

```python
            if settings.extract_enabled and new:
                prov = provider or get_provider(settings)
                for article in articles_repo.list_new_since(db, started):
                    try:
                        extract_article(db, article, prov, settings)
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"文章 {article.id} 提取失败: {exc}")
            if settings.market_symbols and (task.category is None or task.category == "finance"):
                try:
                    snap = run_snapshots(db, settings, client=client)
                    errors.extend(f"行情: {e}" for e in snap["errors"])
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"行情快照失败: {exc}")
```

同时修改 import：

```python
from app.repositories import articles as articles_repo
from app.services.extraction.extractor import extract_article
from app.services.marketdata import run_snapshots
```

注：`run_snapshots` 需要真实 HTTP 客户端时传 `client`；手动执行场景由调用方传入，定时任务默认新建（marketdata 内部已处理）。

- [ ] **Step 5: 运行通过**

Run: `cd backend && uv run pytest tests/test_flow.py -q`
Expected: 4 passed。

- [ ] **Step 6: 提交**

```bash
git add backend/app/repositories/articles.py backend/app/services/flow.py backend/tests/test_flow.py
git commit -m "feat(backend): flow 接入提取与行情"
```

---

### Task 7: 板块查询 API 与审核 API

**Files:**
- Create: `backend/app/api/routes_boards.py`
- Create: `backend/app/api/routes_moderations.py`
- Test: `backend/tests/test_api_boards_moderations.py`

- [ ] **Step 1: 写失败测试**

```python
from datetime import datetime, timezone

from app.models.entities import Category
from app.repositories import indicators, snapshots, sources, stances, timeline, weapons
from app.repositories import articles


def _seed(client):
    with client.app.state.session_factory() as db:
        src = sources.create_source(db, name="S", url="https://example.com/rss",
                                    feed_type="rss", lang="en",
                                    categories=[Category.politics.value, Category.military.value,
                                                Category.economy.value, Category.finance.value])
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        articles.insert_articles(db, [
            dict(source_id=src.id, category="politics", url="https://example.com/a",
                 title="A", summary="s", content_text="", published_at=now,
                 lang="en", dedupe_hash="ha"),
        ])
        art = articles.list_articles(db, category="politics")[0]
        timeline.upsert_event(db, category="politics", subtype="外交与峰会",
                              actor="美日韩", region="亚太", summary="会晤",
                              verification_status="confirmed", article_id=art.id,
                              merge_key="e1")
        timeline.upsert_event(db, category="military", subtype="冲突进展",
                              actor="乌方", region="俄乌", summary="推进",
                              verification_status="draft", article_id=art.id,
                              merge_key="e2")
        weapons.upsert_weapon(db, name="验证机", origin="美国", weapon_type="战斗机",
                              params_text="参数待核", lifecycle_status="研发",
                              merge_key="w1", verification_status="draft",
                              article_id=art.id)
        indicators.upsert_indicator(db, indicator="CPI", region="中国", period="2026-08",
                                    value=0.4, unit="%", merge_key="i1", article_id=art.id)
        stances.create_stance(db, topic="对华", actor="美国商务部", stance_text="扩大",
                              tone="趋严", stated_at=now,
                              verification_status="confirmed", article_id=art.id)
        snapshots.insert_snapshots(db, [
            dict(asset_code="^spx", asset_name="标普500", asset_class="index",
                 price=5980.0, batch_id="b1", source="stooq"),
        ])


def test_board_endpoints(client):
    _seed(client)
    tl = client.get("/api/categories/politics/timeline").json()
    assert len(tl["items"]) == 1 and tl["items"][0]["verification_status"] == "confirmed"
    st = client.get("/api/politics/stances?topic=对华").json()
    assert st["items"][0]["tone"] == "趋严"
    wp = client.get("/api/military/weapons").json()
    assert wp["items"][0]["lifecycle_status"] == "研发"
    ind = client.get("/api/economy/indicators?indicator=CPI").json()
    assert ind["items"][0]["value"] == 0.4
    sn = client.get("/api/finance/snapshots?batch_id=b1").json()
    assert sn["items"][0]["price"] == 5980.0


def test_moderation_flow(client):
    _seed(client)
    queue = client.get("/api/moderations").json()["items"]
    types = {(item["type"], item["id"]) for item in queue}
    assert ("weapon", 1) in types and ("timeline", 2) in types

    resp = client.patch("/api/moderations/weapon/1",
                        json={"action": "confirm"})
    assert resp.status_code == 200 and resp.json()["verification_status"] == "confirmed"

    tl_id = next(item["id"] for item in queue if item["type"] == "timeline")
    edited = client.patch(f"/api/moderations/timeline/{tl_id}",
                          json={"action": "edit", "summary": "已修改的进展", "importance": "high"})
    assert edited.status_code == 200 and edited.json()["summary"] == "已修改的进展"

    stance_id = client.get("/api/moderations").json()["items"]
    assert all(item["type"] != "weapon" for item in stance_id)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_api_boards_moderations.py -q`
Expected: FAIL（路由未注册）。

- [ ] **Step 3: 实现 routes_boards.py**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories import indicators as indicators_repo
from app.repositories import snapshots as snapshots_repo
from app.repositories import stances as stances_repo
from app.repositories import timeline as timeline_repo
from app.repositories import weapons as weapons_repo

router = APIRouter(prefix="/api", tags=["boards"])


def _event_out(e) -> dict:
    return {
        "id": e.id, "category": e.category, "subtype": e.subtype, "actor": e.actor,
        "region": e.region, "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
        "summary": e.summary, "importance": e.importance,
        "verification_status": e.verification_status, "group_key": e.group_key,
        "article_id": e.article_id, "updated_at": e.updated_at.isoformat(),
    }


def _weapon_out(w) -> dict:
    return {"id": w.id, "name": w.name, "origin": w.origin, "weapon_type": w.weapon_type,
            "params_text": w.params_text, "lifecycle_status": w.lifecycle_status,
            "verification_status": w.verification_status, "first_seen_at":
            w.first_seen_at.isoformat() if w.first_seen_at else None}


def _indicator_out(i) -> dict:
    return {"id": i.id, "indicator": i.indicator, "region": i.region, "period": i.period,
            "value": i.value, "unit": i.unit, "previous": i.previous, "forecast": i.forecast,
            "released_at": i.released_at.isoformat() if i.released_at else None}


def _stance_out(s) -> dict:
    return {"id": s.id, "topic": s.topic, "actor": s.actor, "stance_text": s.stance_text,
            "tone": s.tone, "stated_at": s.stated_at.isoformat() if s.stated_at else None,
            "verification_status": s.verification_status}


@router.get("/categories/{category}/timeline")
def category_timeline(category: str, subtype: str | None = None,
                      importance: str | None = None,
                      limit: int = Query(default=100, le=200),
                      db: Session = Depends(get_db)) -> dict:
    items = timeline_repo.list_events(db, category=category, subtype=subtype,
                                      verification="confirmed", limit=limit)
    if importance:
        items = [e for e in items if e.importance == importance]
    return {"items": [_event_out(e) for e in items]}


@router.get("/military/weapons")
def military_weapons(lifecycle: str | None = None,
                     limit: int = Query(default=100, le=200),
                     db: Session = Depends(get_db)) -> dict:
    return {"items": [_weapon_out(w) for w in weapons_repo.list_weapons(
        db, lifecycle=lifecycle, verification="confirmed", limit=limit)]}


@router.get("/economy/indicators")
def economy_indicators(indicator: str | None = None, region: str | None = None,
                       limit: int = Query(default=100, le=200),
                       db: Session = Depends(get_db)) -> dict:
    return {"items": [_indicator_out(i) for i in indicators_repo.list_indicators(
        db, indicator=indicator, region=region, limit=limit)]}


@router.get("/politics/stances")
def politics_stances(topic: str | None = None, actor: str | None = None,
                     limit: int = Query(default=200, le=500),
                     db: Session = Depends(get_db)) -> dict:
    rows = stances_repo.list_stances(db, topic=topic, actor=actor,
                                     verification="confirmed", limit=limit)
    latest: dict[tuple, object] = {}
    for row in rows:
        key = (row.topic, row.actor)
        latest.setdefault(key, row)
    return {"items": [_stance_out(s) for s in latest.values()]}


@router.get("/finance/snapshots")
def finance_snapshots(batch_id: str | None = None, asset_class: str | None = None,
                      limit: int = Query(default=200, le=500),
                      db: Session = Depends(get_db)) -> dict:
    return {"items": [{"id": s.id, "asset_code": s.asset_code, "asset_name": s.asset_name,
                       "asset_class": s.asset_class, "price": s.price,
                       "change_pct": s.change_pct,
                       "captured_at": s.captured_at.isoformat(), "batch_id": s.batch_id,
                       "source": s.source}
                      for s in snapshots_repo.list_snapshots(
                          db, batch_id=batch_id, asset_class=asset_class, limit=limit)]}
```

- [ ] **Step 4: 实现 routes_moderations.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories import indicators as indicators_repo
from app.repositories import stances as stances_repo
from app.repositories import timeline as timeline_repo
from app.repositories import weapons as weapons_repo

router = APIRouter(prefix="/api/moderations", tags=["moderations"])


class ModerationPatch(BaseModel):
    action: str  # confirm | edit | reject
    value: float | None = None
    summary: str | None = None
    importance: str | None = None
    params_text: str | None = None
    lifecycle_status: str | None = None
    stance_text: str | None = None
    tone: str | None = None


def _queue_rows(db: Session, category: str | None, limit: int) -> list[dict]:
    rows = []
    for event in timeline_repo.list_events(db, category=category,
                                           verification="draft", limit=limit):
        rows.append({"type": "timeline", "id": event.id,
                     "category": event.category, "subtype": event.subtype,
                     "summary": event.summary, "importance": event.importance,
                     "verification_status": event.verification_status})
    for weapon in weapons_repo.list_weapons(db, verification="draft", limit=limit):
        rows.append({"type": "weapon", "id": weapon.id, "name": weapon.name,
                     "origin": weapon.origin, "params_text": weapon.params_text,
                     "lifecycle_status": weapon.lifecycle_status,
                     "verification_status": weapon.verification_status})
    for stance in stances_repo.list_stances(db, verification="draft", limit=limit):
        rows.append({"type": "stance", "id": stance.id, "topic": stance.topic,
                     "actor": stance.actor, "stance_text": stance.stance_text,
                     "tone": stance.tone, "verification_status": stance.verification_status})
    for indicator in indicators_repo.list_indicators(db, limit=limit):
        if indicator.verification_status == "draft":
            rows.append({"type": "indicator", "id": indicator.id,
                         "indicator": indicator.indicator, "region": indicator.region,
                         "period": indicator.period, "value": indicator.value,
                         "verification_status": indicator.verification_status})
    return rows


@router.get("")
def list_moderations(category: str | None = None,
                     limit: int = Query(default=100, le=500),
                     db: Session = Depends(get_db)) -> dict:
    return {"items": _queue_rows(db, category, limit)}


def _target(db: Session, type_: str, item_id: int):
    if type_ == "timeline":
        row = timeline_repo.get_event(db, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail="不存在")
        if payload.action == "confirm":
            return timeline_repo.update_event(db, row, verification_status="confirmed")
        if payload.action == "reject":
            return timeline_repo.update_event(db, row, verification_status="rejected")
        return timeline_repo.update_event(db, row, summary=payload.summary,
                                          importance=payload.importance)
    if type_ == "weapon":
        row = weapons_repo.get_weapon(db, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail="不存在")
        if payload.action == "confirm":
            return weapons_repo.update_weapon(db, row, verification_status="confirmed")
        if payload.action == "reject":
            return weapons_repo.update_weapon(db, row, verification_status="rejected")
        return weapons_repo.update_weapon(db, row, params_text=payload.params_text,
                                          lifecycle_status=payload.lifecycle_status)
    if type_ == "stance":
        row = stances_repo.get_stance(db, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail="不存在")
        if payload.action == "confirm":
            return stances_repo.update_stance(db, row, verification_status="confirmed")
        if payload.action == "reject":
            return stances_repo.update_stance(db, row, verification_status="rejected")
        return stances_repo.update_stance(db, row, stance_text=payload.stance_text,
                                          tone=payload.tone)
    if type_ == "indicator":
        row = indicators_repo.get_indicator(db, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail="不存在")
        if payload.action == "confirm":
            return indicators_repo.update_indicator(db, row, verification_status="confirmed")
        if payload.action == "reject":
            return indicators_repo.update_indicator(db, row, verification_status="rejected")
        return indicators_repo.update_indicator(db, row, value=payload.value)
    raise HTTPException(status_code=400, detail=f"未知类型: {type_}")


@router.patch("/{type_}/{item_id}")
def patch_moderation(type_: str, item_id: int, payload: ModerationPatch,
                     db: Session = Depends(get_db)):
    if payload.action not in {"confirm", "reject", "edit"}:
        raise HTTPException(status_code=400, detail="action 必须为 confirm/reject/edit")
    if type_ not in {"timeline", "weapon", "stance", "indicator"}:
        raise HTTPException(status_code=400, detail="type 必须为 timeline/weapon/stance/indicator")
    if type_ == "indicator":
        from app.api.routes_boards import _indicator_out

        return _indicator_out(_target(db, type_, item_id))
    if type_ == "stance":
        from app.api.routes_boards import _stance_out

        return _stance_out(_target(db, type_, item_id))
    if type_ == "weapon":
        from app.api.routes_boards import _weapon_out

        return _weapon_out(_target(db, type_, item_id))
    from app.api.routes_boards import _event_out

    return _event_out(_target(db, type_, item_id))
```

需同步给 `stances_repo` 增加 `get_stance`：

```python
def get_stance(db: Session, stance_id: int) -> StanceTopic | None:
    return db.get(StanceTopic, stance_id)
```

- [ ] **Step 5: main.py 注册两个路由**

```python
from app.api import routes_boards, routes_moderations
...
app.include_router(routes_boards.router)
app.include_router(routes_moderations.router)
```

- [ ] **Step 6: 运行通过**

Run: `cd backend && uv run pytest tests/test_api_boards_moderations.py -q`
Expected: 2 passed。

- [ ] **Step 7: 提交**

```bash
git add backend/app/api/routes_boards.py backend/app/api/routes_moderations.py
git add backend/app/repositories/stances.py backend/app/main.py
git add backend/tests/test_api_boards_moderations.py
git commit -m "feat(backend): 板块查询与审核 API"
```

---

### Task 8: 全量验收与收尾

**Files:**
- Modify: `backend/README.md`（追加新 API 一行）

- [ ] **Step 1: 全量测试**

Run: `cd backend && uv run pytest -q`
Expected: 通过且 0 failed（既有 32 + 新增：models 1、domain_repos 5、rules 4、extractor 3、marketdata 2、flow 1、boards/moderations 2 = 50；计数以实际为准）。

- [ ] **Step 2: README 追加 API 段**

```markdown
## 板块结构化与审核 API

- `GET /api/categories/{cat}/timeline` 事件时间线
- `GET /api/military/weapons`、`GET /api/economy/indicators`
- `GET /api/politics/stances`、`GET /api/finance/snapshots`
- `GET /api/moderations`、`PATCH /api/moderations/{type}/{id}`（confirm/edit/reject）
```

- [ ] **Step 3: 提交**

```bash
git add backend/README.md
git commit -m "docs: R1 API 说明"
```

- [ ] **Step 4: 真实行情标的自查（有网时执行）**

```bash
uv run python - <<'PY'
from app.core.config import Settings
from app.core.database import make_engine, make_session_factory, Base
from app.services.marketdata import StooqCsvProvider
import httpx

settings = Settings(_env_file=None, market_symbols="index|标普500=^spx")
with httpx.Client(timeout=15) as c:
    print(StooqCsvProvider().fetch(c, ["index|标普500=^spx"]))
PY
```

若 `^spx` 不可用，把 `.env` 中 `MARKET_SYMBOLS` 换成可用的 Stooq 代码（实施时可再探测 10usy.b / xau / cl.f 等）并在 README 记录最终清单。

---

## 计划范围说明

- R1 只做结构化数据与提取，不改动四套每日报告模板（属 R2）；`analyses` 现有通用模板在 R2 替换。
- 说明一个落地约定：importance 作为展示估计值写入自动确认条目，不单独进“待确认”队列（避免所有行都进队列）；如需修正可在页面编辑。
- 既有开发库 `data/aurora.db` 需删除后重建（新表由 create_all 建），无迁移脚本；生产不存在存量数据。

## 实施期调整（2026-09-15）

- Task 5 原计划默认 `StooqCsvProvider`；实测 Stooq `/q/l/` 已 404、Yahoo chart 在当前网络不可用，东方财富批量接口可用。
- 调整：新增 `EastmoneyProvider`（单次批量请求 + 单资产缺失降级）并设为默认（`MARKET_PROVIDER=eastmoney`），Stooq 保留为备选；Provider 接口统一为 `fetch(client, specs) -> (rows, errors)`。
- `MARKET_SYMBOLS` 默认留空，行情功能按需启用；相关单测改为东方财富 fixture + Stooq 降级两个用例。
