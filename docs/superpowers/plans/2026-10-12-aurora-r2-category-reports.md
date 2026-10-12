# Aurora R2 实施计划（四套板块每日报告与快讯模板）

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development（本会话子代理通道不可用时改用 superpowers:executing-plans）。Steps 使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 把四大板块的每日分析与快讯从“通用五段式”改造成四套差异化模板：各自的标题、固定章节、板块侧重，并把 R1 已入库的结构化数据（武器档案 / 事件时间线 / 议题立场 / 宏观指标 / 市场快照）注入提示词作为写作素材。

**Architecture:** 新增 `backend/app/services/reports/` 包，按职责拆三个文件：`specs.py` 只放四板块的文案与栏目定义（配置化，改文案不动逻辑）、`context.py` 只负责从仓储装配结构化上下文、`prompts.py` 只负责拼提示词。`analyzer.py` 退化为“取素材 → 调用报告模板 → 落库 → 关联引用”，不再内嵌任何板块文案。

**Tech Stack:** 沿用 Python 3.12 + FastAPI + SQLAlchemy 2 + pytest，无新增依赖。

---

## 文件结构（新增/修改）

```
backend/app/services/reports/__init__.py     # 新增：对外导出 spec_for / build_daily_prompt / build_brief_prompt
backend/app/services/reports/specs.py        # 新增：ReportSpec 与四板块文案、栏目、侧重
backend/app/services/reports/context.py      # 新增：结构化上下文装配（查库 + 格式化）
backend/app/services/reports/prompts.py      # 新增：每日/快讯提示词组装 + 材料编号
backend/app/repositories/snapshots.py        # 修改：新增 recent_batch_ids 供“较上轮”对比
backend/app/services/analyzer.py             # 修改：改用报告模板，删除内嵌文案
backend/tests/test_report_specs.py           # 新增
backend/tests/test_report_context.py         # 新增
backend/tests/test_report_prompts.py         # 新增
backend/tests/test_analyzer.py               # 修改：断言标题与提示词按板块切换
backend/tests/test_flow.py                   # 修改：断言每日分析标题为板块化标题
README.md                                    # 修改：补充四套报告模板说明
docs/superpowers/specs/2026-09-08-aurora-category-differentiation-design.md  # 修改：§6 标注已实现
```

---

### Task 1: 四板块报告规范（specs）

**Files:**
- Create: `backend/app/services/reports/specs.py`
- Create: `backend/app/services/reports/__init__.py`
- Test: `backend/tests/test_report_specs.py`

- [ ] **Step 1: 写失败测试** `backend/tests/test_report_specs.py`

```python
from app.core.constants import ALL_CATEGORIES
from app.services.reports.specs import REPORT_SPECS, spec_for


def test_all_categories_have_spec():
    assert set(REPORT_SPECS) == set(ALL_CATEGORIES)


def test_daily_titles_are_category_specific():
    titles = {spec_for(c).daily_title for c in ALL_CATEGORIES}
    assert titles == {"政治每日综述", "军事态势简报", "宏观与政策简报", "市场复盘"}


def test_sections_are_distinct_between_categories():
    seen = [tuple(spec_for(c).daily_sections) for c in ALL_CATEGORIES]
    assert len(set(seen)) == len(seen)
    assert spec_for("military").daily_sections[1] == "新武器与装备动态"
    assert spec_for("economy").daily_sections[0] == "数据要点"
    assert spec_for("finance").daily_sections[0] == "资产表现"


def test_structured_blocks_match_board_features():
    assert spec_for("politics").structured_blocks == ("timeline", "stances")
    assert spec_for("military").structured_blocks == ("weapons", "timeline")
    assert spec_for("economy").structured_blocks == ("indicators", "timeline")
    assert spec_for("finance").structured_blocks == ("snapshots", "timeline")


def test_unknown_category_raises():
    import pytest

    with pytest.raises(KeyError):
        spec_for("sports")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_report_specs.py -q`
Expected: FAIL（`ModuleNotFoundError: app.services.reports`）

- [ ] **Step 3: 实现** `backend/app/services/reports/specs.py`

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportSpec:
    """单个板块的报告规范：文案、栏目、侧重与需要注入的结构化区块。"""

    category: str
    label: str
    daily_title: str
    daily_sections: tuple[str, ...]
    daily_focus: str
    brief_focus: str
    structured_blocks: tuple[str, ...]


REPORT_SPECS: dict[str, ReportSpec] = {
    "politics": ReportSpec(
        category="politics",
        label="政治",
        daily_title="政治每日综述",
        daily_sections=("今日要闻", "事件脉络", "议题立场变化", "下一步看点"),
        daily_focus=(
            "读者关心「谁在做决定、为什么、下一步会怎样」。按时间顺序梳理决定与表态，"
            "指出各方立场的变化方向，并给出可验证的下一步观察点。"
        ),
        brief_focus="聚焦当天最重要的政治决定、表态与外交动作，说明其影响对象与后续走向。",
        structured_blocks=("timeline", "stances"),
    ),
    "military": ReportSpec(
        category="military",
        label="军事",
        daily_title="军事态势简报",
        daily_sections=("态势要点", "新武器与装备动态", "冲突进展", "演习·军贸·防务快讯", "态势展望"),
        daily_focus=(
            "读者关心「谁有了什么新武器、仗打到哪一步」。装备条目要给出可核实的名称、国别、"
            "类型、状态与已知参数；冲突按战线分条推进，明确控制区或打击范围的变化。"
        ),
        brief_focus="聚焦新装备动态与冲突战线进展，只写有材料支撑的事实性变化。",
        structured_blocks=("weapons", "timeline"),
    ),
    "economy": ReportSpec(
        category="economy",
        label="经济",
        daily_title="宏观与政策简报",
        daily_sections=("数据要点", "政策动作与影响对象", "机构预测调整", "传导提示"),
        daily_focus=(
            "读者关心「数据说明现状、政策指明方向」。数据要点须写明数值、前值、预期与超预期/"
            "不及预期判断；政策动作写明执行机构、工具与直接影响对象。"
        ),
        brief_focus="聚焦当天的数据发布与政策动作，说明方向性含义与受影响行业。",
        structured_blocks=("indicators", "timeline"),
    ),
    "finance": ReportSpec(
        category="finance",
        label="金融",
        daily_title="市场复盘",
        daily_sections=("资产表现", "驱动事件归因", "资金与风险信号", "明日关注"),
        daily_focus=(
            "读者关心「价格怎么变、为什么变、风险在哪」。资产表现按板块与资产类别列出涨跌幅，"
            "归因只能引用材料中出现的驱动因素，风险信号要指出具体指标或事件。"
        ),
        brief_focus="聚焦主要市场涨跌与驱动因素，标明风险信号。",
        structured_blocks=("snapshots", "timeline"),
    ),
}


def spec_for(category: str) -> ReportSpec:
    spec = REPORT_SPECS.get(category)
    if spec is None:
        raise KeyError(f"未知板块: {category}")
    return spec
```

- [ ] **Step 4: 实现** `backend/app/services/reports/__init__.py`

```python
from app.services.reports.specs import REPORT_SPECS, ReportSpec, spec_for

__all__ = ["REPORT_SPECS", "ReportSpec", "spec_for"]
```

（Task 3 会把 `build_daily_prompt` / `build_brief_prompt` 追加到导出列表。）

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && uv run pytest tests/test_report_specs.py -q`
Expected: `5 passed`

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/reports backend/tests/test_report_specs.py
git commit -m "feat(backend): 四板块报告规范与栏目定义"
```

---

### Task 2: 结构化上下文装配（context）

**Files:**
- Modify: `backend/app/repositories/snapshots.py`
- Create: `backend/app/services/reports/context.py`
- Test: `backend/tests/test_report_context.py`

- [ ] **Step 1: 写失败测试** `backend/tests/test_report_context.py`

```python
from datetime import datetime

from app.repositories import indicators, snapshots, stances, timeline, weapons
from app.services.reports.context import build_board_context
from app.services.reports.specs import spec_for


def _seed_structured(db):
    timeline.upsert_event(
        db, category="military", subtype="冲突进展", actor="双方", region="俄乌",
        occurred_at=datetime(2026, 10, 11, 9, 0), summary="东部战线推进 3 公里",
        importance="high", verification_status="confirmed", merge_key="ev1",
    )
    timeline.upsert_event(
        db, category="military", subtype="冲突进展", actor="双方", region="俄乌",
        summary="未经证实的草稿事件", verification_status="draft", merge_key="ev2",
    )
    weapons.upsert_weapon(db, name="PrSM", origin="美国", weapon_type="导弹",
                          lifecycle_status="测试", params_text="射程 499 公里",
                          verification_status="confirmed", merge_key="w1")
    indicators.upsert_indicator(db, indicator="CPI", region="中国", period="2026-09",
                                value=0.4, unit="%", previous=0.5, forecast=0.3,
                                merge_key="i1")
    snapshots.insert_snapshots(db, [
        dict(asset_code="100.SPX", asset_name="标普500", asset_class="index",
             price=5800.0, change_pct=1.2, captured_at=datetime(2026, 10, 11, 21, 0),
             batch_id="b1", source="eastmoney"),
        dict(asset_code="100.NDX", asset_name="纳斯达克", asset_class="index",
             price=20300.0, change_pct=-0.4, captured_at=datetime(2026, 10, 11, 21, 0),
             batch_id="b1", source="eastmoney"),
        dict(asset_code="100.SPX", asset_name="标普500", asset_class="index",
             price=5730.0, change_pct=0.3, captured_at=datetime(2026, 10, 10, 21, 0),
             batch_id="b0", source="eastmoney"),
    ])
    stances.create_stance(db, topic="俄乌", actor="美国国务院", stance_text="继续援乌",
                          tone="支持", stated_at=datetime(2026, 10, 11, 10, 0),
                          verification_status="confirmed")


def test_military_context_contains_weapons_and_confirmed_events_only(db):
    _seed_structured(db)
    text = build_board_context(db, spec_for("military"))
    assert "### 武器档案" in text and "PrSM" in text
    assert "东部战线推进 3 公里" in text
    assert "未经证实的草稿事件" not in text


def test_economy_context_contains_indicator_numbers(db):
    _seed_structured(db)
    text = build_board_context(db, spec_for("economy"))
    assert "CPI" in text and "0.4" in text and "前值 0.5" in text and "预期 0.3" in text


def test_finance_context_compares_with_previous_batch(db):
    _seed_structured(db)
    text = build_board_context(db, spec_for("finance"))
    assert "标普500" in text and "上轮涨跌 0.30%" in text and "+1.20%" in text


def test_politics_context_carries_stances(db):
    _seed_structured(db)
    text = build_board_context(db, spec_for("politics"))
    assert "### 议题立场" in text and "美国国务院" in text and "继续援乌" in text


def test_empty_database_returns_empty_string(db):
    assert build_board_context(db, spec_for("military")) == ""
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_report_context.py -q`
Expected: FAIL（`ModuleNotFoundError: app.services.reports.context`）

- [ ] **Step 3: 给快照仓储加批次查询** `backend/app/repositories/snapshots.py`（追加到文件末尾）

```python
def recent_batch_ids(db: Session, limit: int = 2) -> list[str]:
    """按抓取时间倒序返回最近的批次 id，用于「较上轮」对比。"""

    rows = (
        db.query(MarketSnapshot.batch_id, MarketSnapshot.captured_at)
        .order_by(MarketSnapshot.captured_at.desc())
        .limit(200)
        .all()
    )
    ids: list[str] = []
    for batch_id, _ in rows:
        if batch_id and batch_id not in ids:
            ids.append(batch_id)
        if len(ids) >= limit:
            break
    return ids
```

- [ ] **Step 4: 实现** `backend/app/services/reports/context.py`

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories import indicators as indicators_repo
from app.repositories import snapshots as snapshots_repo
from app.repositories import stances as stances_repo
from app.repositories import timeline as timeline_repo
from app.repositories import weapons as weapons_repo
from app.services.reports.specs import ReportSpec

BLOCK_LIMIT = 20


def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}%"


def _timeline_block(db: Session, category: str) -> str:
    events = timeline_repo.list_events(
        db, category=category, verification="confirmed", limit=BLOCK_LIMIT
    )
    if not events:
        return ""
    lines = ["### 事件时间线（本系统已确认条目）"]
    for e in events:
        when = f"{e.occurred_at:%Y-%m-%d}" if e.occurred_at else "日期未定"
        lines.append(
            f"- {when} | {e.subtype} | {e.actor or '—'} | {e.region or '—'} | "
            f"[{e.importance}] {e.summary}"
        )
    return "\n".join(lines)


def _weapons_block(db: Session) -> str:
    rows = weapons_repo.list_weapons(db, verification="confirmed", limit=BLOCK_LIMIT)
    if not rows:
        return ""
    lines = ["### 武器档案（本系统已确认条目）"]
    for w in rows:
        params = (w.params_text or "").replace("\n", " / ")
        line = (
            f"- {w.name}" + (f"（{w.original_name}）" if w.original_name else "")
            + f" | {w.origin or '—'} | {w.weapon_type or '—'} | {w.lifecycle_status or '—'}"
        )
        if params:
            line += f" | 参数: {params}"
        lines.append(line)
    return "\n".join(lines)


def _stances_block(db: Session) -> str:
    rows = stances_repo.list_stances(db, verification="confirmed", limit=BLOCK_LIMIT)
    if not rows:
        return ""
    lines = ["### 议题立场（本系统已确认条目）"]
    for s in rows:
        when = f"{s.stated_at:%Y-%m-%d}" if s.stated_at else "日期未定"
        lines.append(f"- {when} | {s.topic} | {s.actor} | 基调 {s.tone} | {s.stance_text}")
    return "\n".join(lines)


def _indicators_block(db: Session) -> str:
    rows = indicators_repo.list_indicators(db, limit=BLOCK_LIMIT)
    if not rows:
        return ""
    lines = ["### 宏观指标（本系统已入库条目）"]
    for i in rows:
        parts = [f"{i.region or '—'} {i.period or '—'} {i.indicator} = {i.value}{i.unit or ''}"]
        if i.previous is not None:
            parts.append(f"前值 {i.previous}{i.unit or ''}")
        if i.forecast is not None:
            parts.append(f"预期 {i.forecast}{i.unit or ''}")
        lines.append("- " + " | ".join(parts))
    return "\n".join(lines)


def _snapshots_block(db: Session) -> str:
    batch_ids = snapshots_repo.recent_batch_ids(db, limit=2)
    if not batch_ids:
        return ""
    latest = {s.asset_name: s for s in snapshots_repo.list_snapshots(db, batch_id=batch_ids[0])}
    previous = (
        {s.asset_name: s for s in snapshots_repo.list_snapshots(db, batch_id=batch_ids[1])}
        if len(batch_ids) > 1
        else {}
    )
    lines = [f"### 市场快照（批次 {batch_ids[0]}）"]
    for name, snap in sorted(latest.items(), key=lambda kv: kv[1].asset_class or ""):
        line = (
            f"- {snap.asset_class or '—'} | {name} | 价格 {snap.price} | "
            f"本批次 {_fmt_pct(snap.change_pct)}"
        )
        prev = previous.get(name)
        if prev is not None:
            line += f" | 上轮涨跌 {_fmt_pct(prev.change_pct)} | 上轮价格 {prev.price}"
        lines.append(line)
    return "\n".join(lines)


_BLOCK_BUILDERS = {
    "timeline": lambda db, spec: _timeline_block(db, spec.category),
    "weapons": lambda db, spec: _weapons_block(db),
    "stances": lambda db, spec: _stances_block(db),
    "indicators": lambda db, spec: _indicators_block(db),
    "snapshots": lambda db, spec: _snapshots_block(db),
}


def build_board_context(db: Session, spec: ReportSpec) -> str:
    """按板块规范装配结构化上下文；无数据时返回空字符串。"""

    blocks = [
        _BLOCK_BUILDERS[name](db, spec)
        for name in spec.structured_blocks
        if name in _BLOCK_BUILDERS
    ]
    return "\n\n".join(block for block in blocks if block)
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && uv run pytest tests/test_report_context.py -q`
Expected: `5 passed`

- [ ] **Step 6: 提交**

```bash
git add backend/app/repositories/snapshots.py backend/app/services/reports/context.py backend/tests/test_report_context.py
git commit -m "feat(backend): 板块结构化上下文装配"
```

---

### Task 3: 提示词组装（prompts）

**Files:**
- Create: `backend/app/services/reports/prompts.py`
- Modify: `backend/app/services/reports/__init__.py`
- Test: `backend/tests/test_report_prompts.py`

- [ ] **Step 1: 写失败测试** `backend/tests/test_report_prompts.py`

```python
from datetime import datetime

from app.core.config import Settings
from app.repositories import indicators
from app.services.reports.prompts import build_brief_prompt, build_daily_prompt


class _Article:
    def __init__(self, title="A", body="body", source_name="S"):
        self.title = title
        self.summary = ""
        self.content_text = body
        self.source = type("Src", (), {"name": source_name})()
        self.fetched_at = datetime(2026, 10, 11, 8, 0)


def test_daily_prompt_lists_board_sections(db):
    settings = Settings(_env_file=None)
    prompt = build_daily_prompt(db, "military", [_Article()], settings)
    assert "军事态势简报" in prompt
    for section in ("## 态势要点", "## 新武器与装备动态", "## 冲突进展",
                    "## 演习·军贸·防务快讯", "## 态势展望", "## 资料来源"):
        assert section in prompt
    assert "[1]" in prompt


def test_daily_prompt_sections_differ_per_category(db):
    settings = Settings(_env_file=None)
    materials = [_Article()]
    politics = build_daily_prompt(db, "politics", materials, settings)
    finance = build_daily_prompt(db, "finance", materials, settings)
    assert "## 议题立场变化" in politics and "## 资产表现" not in politics
    assert "## 资产表现" in finance and "## 议题立场变化" not in finance


def test_brief_prompt_uses_board_focus(db):
    settings = Settings(_env_file=None)
    prompt = build_brief_prompt(db, "finance", [_Article()], settings)
    assert "金融" in prompt and "3~5 条" in prompt
    assert "**事件：**" in prompt and "**影响：**" in prompt and "**来源：**" in prompt
    assert "市场涨跌与驱动因素" in prompt


def test_daily_prompt_includes_structured_context_when_present(db):
    settings = Settings(_env_file=None)
    indicators.upsert_indicator(db, indicator="CPI", region="中国", period="2026-09",
                                value=0.4, unit="%", merge_key="i1")
    prompt = build_daily_prompt(db, "economy", [_Article()], settings)
    assert "### 宏观指标" in prompt and "CPI" in prompt


def test_materials_are_truncated_by_settings(db):
    settings = Settings(_env_file=None, max_analysis_input_chars=10)
    prompt = build_daily_prompt(db, "politics", [_Article(body="x" * 500)], settings)
    assert "x" * 11 not in prompt
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_report_prompts.py -q`
Expected: FAIL（`ModuleNotFoundError: app.services.reports.prompts`）

- [ ] **Step 3: 实现** `backend/app/services/reports/prompts.py`

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.reports.context import build_board_context
from app.services.reports.specs import spec_for

CONTEXT_HEADER = "【板块结构化数据（来自本系统已确认条目，与材料冲突时以材料为准）】"


def _numbered_materials(articles, max_chars: int) -> str:
    lines = []
    for i, art in enumerate(articles, start=1):
        body = (art.summary or art.content_text or "")[:max_chars]
        lines.append(
            f"[{i}] 站点:{art.source.name if art.source else 'unknown'} | "
            f"时间:{art.fetched_at:%Y-%m-%d %H:%M} | 标题:{art.title}\n正文:{body}"
        )
    return "\n\n".join(lines)


def _context_part(db: Session, category: str) -> str:
    context = build_board_context(db, spec_for(category))
    return f"\n\n{CONTEXT_HEADER}\n{context}" if context else ""


def build_brief_prompt(db: Session, category: str, materials, settings: Settings) -> str:
    spec = spec_for(category)
    return (
        f"你是面向投资与研究的板块简报助手。基于以下 {len(materials)} 条材料（编号 [n] 对应材料），"
        f"用中文写「{spec.label}」板块快讯要点，3~5 条。{spec.brief_focus}\n"
        "每条格式：\n**事件：**一句话\n**影响：**对市场/政策/局势的提示\n**来源：**站点名称\n"
        "只能基于给定材料，禁止编造。"
        + _context_part(db, category)
        + "\n\n材料：\n"
        + _numbered_materials(materials, settings.max_analysis_input_chars)
    )


def build_daily_prompt(db: Session, category: str, materials, settings: Settings) -> str:
    spec = spec_for(category)
    sections = "\n".join(f"## {name}" for name in spec.daily_sections)
    return (
        f"你是严谨的宏观研究与投资参考分析师。基于以下 {len(materials)} 条编号材料"
        f"（[n] 站点 | 时间 | 标题 | 正文），为「{spec.label}」板块写一篇 1500~2500 字中文"
        f"《{spec.daily_title}》，Markdown 格式，固定章节：\n"
        f"{sections}\n## 资料来源\n"
        f"写作要求：{spec.daily_focus}\n"
        "规则：只能引用给定材料；资料来源逐行写 `- 编号 站点 · 标题`；"
        "禁止编造来源、数据与机构表态。"
        + _context_part(db, category)
        + "\n\n材料：\n"
        + _numbered_materials(materials, settings.max_analysis_input_chars)
    )
```

- [ ] **Step 4: 更新导出** `backend/app/services/reports/__init__.py`

```python
from app.services.reports.prompts import build_brief_prompt, build_daily_prompt
from app.services.reports.specs import REPORT_SPECS, ReportSpec, spec_for

__all__ = [
    "REPORT_SPECS",
    "ReportSpec",
    "build_brief_prompt",
    "build_daily_prompt",
    "spec_for",
]
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && uv run pytest tests/test_report_prompts.py -q`
Expected: `5 passed`

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/reports backend/tests/test_report_prompts.py
git commit -m "feat(backend): 四板块每日与快讯提示词组装"
```

---

### Task 4: 分析器接入模板

**Files:**
- Modify: `backend/app/services/analyzer.py`
- Test: `backend/tests/test_analyzer.py`
- Test: `backend/tests/test_flow.py`

- [ ] **Step 1: 追加失败测试** `backend/tests/test_analyzer.py`

在 `FakeProvider` 之后追加可捕获提示词的子类：

```python
class CapturingProvider(FakeProvider):
    def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
        self.last_prompt = messages[-1]["content"]
        return self.text
```

文件末尾追加两个测试：

```python
def test_daily_title_and_prompt_follow_board_spec(db):
    from app.core.config import Settings

    now = _seed_material(db)
    settings = Settings(_env_file=None)
    md = "## 数据要点\n- 结论\n\n## 资料来源\n- 1 S · Fed moves"
    provider = CapturingProvider(settings, md)
    result = generate_daily(db, "economy", provider, settings, until=now + timedelta(seconds=5))
    assert result is not None
    assert result.title.startswith("宏观与政策简报 · ")
    assert "## 数据要点" in provider.last_prompt
    assert "## 资产表现" not in provider.last_prompt


def test_brief_title_uses_board_label(db):
    from app.core.config import Settings

    now = _seed_material(db)
    settings = Settings(_env_file=None)
    provider = FakeProvider(settings, "- **事件**：x\n  **影响**：y\n  **来源**：S")
    result = generate_brief(db, "economy", provider, settings, since=now - timedelta(hours=1))
    assert result is not None and result.title.startswith("经济快讯 ")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_analyzer.py -q`
Expected: FAIL（标题仍是 `经济每日分析 ...`，提示词是通用五段式）

- [ ] **Step 3: 改写** `backend/app/services/analyzer.py`（整文件替换）

```python
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import Analysis, Category
from app.repositories import analyses as analyses_repo
from app.repositories import articles as articles_repo
from app.services.llm import ChatProvider
from app.services.reports import build_brief_prompt, build_daily_prompt, spec_for

ALL = [c.value for c in Category]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_citation_ids(content_md: str, max_id: int) -> list[int]:
    section = content_md.rsplit("资料来源", 1)[-1]
    ids = []
    for line in section.splitlines():
        m = re.match(r"^\s*[-*]?\s*(\d+)[.、)）]?\s*", line)
        if not m:
            continue
        n = int(m.group(1))
        if 1 <= n <= max_id and n not in ids:
            ids.append(n)
    return ids


def generate_brief(db: Session, category: str, provider: ChatProvider,
                   settings: Settings, *, since: datetime | None = None) -> Analysis | None:
    until = _now()
    since = since or (until - timedelta(hours=6))
    materials = articles_repo.articles_for_analysis(
        db, category, since, until, limit=settings.top_articles_per_analysis
    )
    if not materials:
        return None
    prompt = build_brief_prompt(db, category, materials, settings)
    content = provider.complete(
        [{"role": "user", "content": prompt}], temperature=0.2, max_tokens=2000
    )
    spec = spec_for(category)
    return analyses_repo.create_analysis(
        db, kind="brief", category=category,
        title=f"{spec.label}快讯 {until:%H:%M}",
        content_md=content, period_start=since, period_end=until,
        model=settings.llm_model,
    )


def generate_daily(db: Session, category: str, provider: ChatProvider,
                   settings: Settings, *, until: datetime | None = None) -> Analysis | None:
    until = until or _now()
    since = until - timedelta(hours=24)
    materials = articles_repo.articles_for_analysis(
        db, category, since, until, limit=settings.top_articles_per_analysis
    )
    if not materials:
        return None
    prompt = build_daily_prompt(db, category, materials, settings)
    content = provider.complete(
        [{"role": "user", "content": prompt}], temperature=0.2, max_tokens=4000
    )
    spec = spec_for(category)
    analysis = analyses_repo.create_analysis(
        db, kind="daily", category=category,
        title=f"{spec.daily_title} · {until:%Y-%m-%d}",
        content_md=content, period_start=since, period_end=until,
        model=settings.llm_model,
    )
    ids = _parse_citation_ids(content, len(materials))
    valid_ids = [materials[i - 1].id for i in ids if i <= len(materials)]
    if valid_ids:
        analyses_repo.link_articles(db, analysis, valid_ids)
    return analysis
```

- [ ] **Step 4: 追加流程断言** `backend/tests/test_flow.py`（在 `test_analyze_flow_creates_daily` 内追加）

```python
    titles = [a.title for a in analyses.list_analyses(db, kind="daily")]
    assert titles and all("·" in t for t in titles)
    assert all("每日分析" not in t for t in titles)
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && uv run pytest tests/test_analyzer.py tests/test_flow.py -q`
Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/analyzer.py backend/tests/test_analyzer.py backend/tests/test_flow.py
git commit -m "feat(backend): 分析器改用四板块报告模板"
```

---

### Task 5: 文档同步与全量回归

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-09-08-aurora-category-differentiation-design.md`

- [ ] **Step 1: README 增加报告模板小节**（插入到“板块结构化与审核 API”之前）

```markdown
## 四板块每日报告模板

每类板块的每日分析（`kind=daily`）与快讯（`kind=brief`）使用各自的标题与固定章节，
由 `backend/app/services/reports/specs.py` 集中定义（改文案不动逻辑）：

| 板块 | 每日报告 | 固定章节 |
| --- | --- | --- |
| 政治 | 政治每日综述 | 今日要闻 / 事件脉络 / 议题立场变化 / 下一步看点 |
| 军事 | 军事态势简报 | 态势要点 / 新武器与装备动态 / 冲突进展 / 演习·军贸·防务快讯 / 态势展望 |
| 经济 | 宏观与政策简报 | 数据要点 / 政策动作与影响对象 / 机构预测调整 / 传导提示 |
| 金融 | 市场复盘 | 资产表现 / 驱动事件归因 / 资金与风险信号 / 明日关注 |

生成提示词会把该板块已确认的结构化条目（武器档案、事件时间线、议题立场、宏观指标、
市场快照）作为附加素材注入，并要求与新闻材料冲突时以材料为准。
```

- [ ] **Step 2: 设计规范标注实现状态**：在 `docs/superpowers/specs/2026-09-08-aurora-category-differentiation-design.md` 的 §6 标题下追加一行

```markdown
> 实现状态：R2 已实现（`backend/app/services/reports/` 定义栏目与提示词，`analyzer.py` 调用）。
```

- [ ] **Step 3: 全量回归**

Run: `cd backend && uv run pytest -q`
Expected: 全部通过（R1 为 52 项，本计划新增约 13 项）

- [ ] **Step 4: 提交**

```bash
git add README.md docs/superpowers/specs/2026-09-08-aurora-category-differentiation-design.md
git commit -m "docs: 补充四板块报告模板说明"
```

---

## 自查清单

- 规范覆盖：§6 四套模板标题与章节（Task 1/3/4）、结构化数据入提示词（Task 2）、快讯差异化（Task 1/3）、测试策略中“报告模板：Fake LLM 输出验证四个板块的标题与章节提示词被正确选用”（Task 1/3/4）
- 无占位符：每个代码步骤都给了完整可粘贴内容
- 命名一致：`spec_for` / `build_board_context` / `build_brief_prompt` / `build_daily_prompt` / `recent_batch_ids` 在计划内保持同名
