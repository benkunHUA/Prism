# Aurora 地区新闻列表中文化与滚动约束 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 看板右栏地区新闻列表改为容器内滚动（面板高度与地图对齐），条目显示中文标题与中文摘要；译文在采集落库阶段由批量 LLM 调用产生。

**Architecture:** 后端在 `articles` 加两个可空列 `title_zh` / `summary_zh`，由 `ensure_schema` 自动补列上线；新增 `app/services/translation/` 做批量翻译（一次请求翻多篇，带 `index` 校验，整批失败时对半拆分重试到单篇），采集流程在抽取之后调用它；前端只做展示层回落与滚动容器。

**Tech Stack:** FastAPI + SQLAlchemy 2 + pytest（后端）；React 18 + Vite + TS + Ant Design 5 + vitest（前端）。

**Spec:** `docs/superpowers/specs/2026-10-13-aurora-region-list-zh-design.md`

**每个任务结束都要跑：** 后端 `cd backend && uv run pytest -q`；前端 `cd frontend && npm test && npm run typecheck`。

---

## 文件结构

**后端新增**

| 文件 | 职责 |
| --- | --- |
| `backend/app/services/translation/__init__.py` | 包标记 |
| `backend/app/services/translation/prompts.py` | 翻译提示词与文案常量（配置外置） |
| `backend/app/services/translation/translator.py` | 批量翻译编排：切批、`index` 校验、减半重试、落库 |
| `backend/scripts/backfill_translations.py` | 存量回填命令，复用同一个 service |
| `backend/tests/test_translation.py` | 翻译 service 单测 |
| `backend/tests/test_serializers.py` | `article_out` 译文字段单测 |

**后端修改**

| 文件 | 改动 |
| --- | --- |
| `backend/app/models/entities.py` | `Article` 加 `title_zh` / `summary_zh` |
| `backend/app/core/config.py` | 加 `translate_enabled` / `translate_batch_size` / `llm_translate_max_tokens` |
| `backend/app/services/flow.py` | 采集分支在抽取后追加翻译 |
| `backend/app/api/serializers.py` | `article_out` 带出译文 |
| `backend/tests/test_schema.py` | 老库补两列的用例 |
| `backend/tests/test_config.py` | 新配置默认值用例 |
| `backend/tests/test_flow.py` | 采集分支翻译 + 失败降级用例 |
| `backend/.env.example` | 新配置项 |

**前端新增**

| 文件 | 职责 |
| --- | --- |
| `frontend/src/utils/article.ts` | 纯函数：译文优先、缺失回落原文 |
| `frontend/src/utils/article.test.ts` | 上面纯函数的单测 |

**前端修改**

| 文件 | 改动 |
| --- | --- |
| `frontend/src/api/types.ts` | `ArticleItem` 加 `title_zh` / `summary_zh` |
| `frontend/src/constants/mapBoard.ts` | 列表容器高度与摘要行数常量 |
| `frontend/src/components/map/RegionPanel.tsx` | 滚动容器 + 中文标题摘要 |

---

## Task 1: `articles` 增加译文列

**Files:**
- Modify: `backend/app/models/entities.py`（`Article` 的 `summary` 之后）
- Test: `backend/tests/test_schema.py`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_schema.py` 末尾（该文件已 import `inspect`、`text`、`make_engine`、`ensure_schema`）：

```python
# 旧版本 articles 表：没有翻译功能引入的 title_zh / summary_zh。
LEGACY_ARTICLES_DDL = """
CREATE TABLE articles (
    id INTEGER NOT NULL PRIMARY KEY,
    source_id INTEGER,
    category VARCHAR(20) NOT NULL,
    url VARCHAR(2000) NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    summary TEXT NOT NULL,
    content_text TEXT NOT NULL,
    published_at DATETIME,
    fetched_at DATETIME NOT NULL,
    dedupe_hash VARCHAR(64) NOT NULL,
    lang VARCHAR(10) NOT NULL
)
"""


def test_ensure_schema_backfills_translation_columns(tmp_path):
    engine = make_engine(str(tmp_path / "legacy_articles.db"))
    with engine.begin() as conn:
        conn.execute(text(LEGACY_ARTICLES_DDL))

    added = ensure_schema(engine)

    assert "articles.title_zh" in added
    assert "articles.summary_zh" in added
    columns = {c["name"] for c in inspect(engine).get_columns("articles")}
    assert {"title_zh", "summary_zh"} <= columns
    engine.dispose()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest -q tests/test_schema.py::test_ensure_schema_backfills_translation_columns`
Expected: FAIL —— `AssertionError`（`articles.title_zh` 不在 `added` 里，因为模型还没这两列）

- [ ] **Step 3: 加两列**

`backend/app/models/entities.py` 的 `Article` 中，把

```python
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text, default="")
```

改成

```python
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text, default="")
    # 译文；缺译文为 NULL，展示层回落原文
    title_zh: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest -q tests/test_schema.py`
Expected: PASS（该文件全部用例通过；老库副本上补列不破坏数据）

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/entities.py backend/tests/test_schema.py
git commit -m "feat(backend): articles 增加 title_zh / summary_zh 两列"
```

---

## Task 2: 翻译相关配置项

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_config.py` 的 `test_defaults` 里追加四行断言（放在 `assert s.extract_enabled is True` 之后）：

```python
    assert s.translate_enabled is True
    assert s.translate_batch_size == 10
    assert s.llm_translate_max_tokens == 3000
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest -q tests/test_config.py`
Expected: FAIL —— `AttributeError: 'Settings' object has no attribute 'translate_enabled'`

- [ ] **Step 3: 加配置**

`backend/app/core/config.py` 中，在 `llm_extract_max_tokens` 那一行之后插入：

```python
    llm_translate_max_tokens: int = 3000
```

再在 `extract_enabled: bool = True` 那一行之后插入：

```python
    # 译文（标题 + 摘要）在采集落库阶段生成；批量调用，一批多少篇
    translate_enabled: bool = True
    translate_batch_size: int = 10
```

- [ ] **Step 4: 补 `.env.example`**

`backend/.env.example` 中，在 `LLM_EXTRACT_MAX_TOKENS=4000` 之后插入：

```dotenv
LLM_TRANSLATE_MAX_TOKENS=3000
```

在 `EXTRACT_ENABLED=true` 之后插入：

```dotenv
# 译文：采集时批量翻译标题与摘要
TRANSLATE_ENABLED=true
TRANSLATE_BATCH_SIZE=10
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && uv run pytest -q tests/test_config.py`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/core/config.py backend/.env.example backend/tests/test_config.py
git commit -m "feat(backend): 翻译开关、批大小与输出预算配置"
```

---

## Task 3: 翻译提示词

**Files:**
- Create: `backend/app/services/translation/__init__.py`
- Create: `backend/app/services/translation/prompts.py`

- [ ] **Step 1: 建包标记**

新建 `backend/app/services/translation/__init__.py`，内容为空文件（与 `app/services/extraction/__init__.py` 一致）。

- [ ] **Step 2: 写提示词模块**

新建 `backend/app/services/translation/prompts.py`：

```python
"""翻译提示词与文案常量。只放字符串与纯函数，不做 IO。"""

from __future__ import annotations

SUMMARY_LIMIT = 120

INSTRUCTION = (
    "把下面每条新闻的标题和摘要翻成简体中文，只做翻译与压缩，不补充原文没有的信息。\n"
    f"summary_zh 是中文要点，不超过 {SUMMARY_LIMIT} 字，不要逐字直译；原文没有摘要时给空字符串。\n"
    "严格输出 JSON 数组，不要输出其它文字，不要加代码块围栏，index 必须与输入的方括号编号一致，"
    "且每条都要出现。\n"
    '格式：[{"index": 0, "title_zh": "...", "summary_zh": "..."}]'
)


def build_translation_prompt(items: list[tuple[int, str, str]]) -> str:
    """items 为 (index, 标题, 摘要)，摘要调用方已截断。"""
    lines = [INSTRUCTION, ""]
    for index, title, summary in items:
        lines.append(f"[{index}] 标题：{title}")
        lines.append(f"[{index}] 摘要：{summary or '（无）'}")
    return "\n".join(lines)
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/translation/__init__.py backend/app/services/translation/prompts.py
git commit -m "feat(backend): 翻译提示词模块"
```

---

## Task 4: 批量翻译 service

**Files:**
- Create: `backend/app/services/translation/translator.py`
- Test: `backend/tests/test_translation.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_translation.py`：

```python
import json

from app.core.config import Settings
from app.models.entities import Article
from app.repositories import articles as articles_repo
from app.repositories import sources as sources_repo
from app.services.llm import ChatProvider
from app.services.translation.translator import translate_articles


class ScriptedProvider(ChatProvider):
    """按调用次序返回预设结果，并记录调用次数。"""

    name = "scripted"

    def __init__(self, settings, script):
        super().__init__(settings)
        self.script = script
        self.calls = 0

    def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
        self.calls += 1
        return self.script(messages, self.calls)


def _articles(db, count: int, *, lang: str = "en") -> list[Article]:
    src = sources_repo.create_source(db, name="S", url="https://example.com/feed",
                                     feed_type="rss", lang="en", categories=["politics"])
    articles_repo.insert_articles(db, [
        dict(source_id=src.id, category="politics", url=f"https://example.com/a{i}",
             title=f"Title {i}", summary=f"Summary {i}", content_text="",
             published_at=None, lang=lang, dedupe_hash=f"h{i}")
        for i in range(count)
    ])
    return articles_repo.list_articles(db)


def _payload(indexes: list[int]) -> str:
    return json.dumps(
        [{"index": i, "title_zh": f"标题{i}", "summary_zh": f"要点{i}"} for i in indexes],
        ensure_ascii=False,
    )


def test_batch_translates_in_one_call(db):
    settings = Settings(_env_file=None, translate_batch_size=10)
    rows = _articles(db, 3)
    provider = ScriptedProvider(settings, lambda messages, call_no: _payload([0, 1, 2]))

    done, errors = translate_articles(db, rows, provider, settings)

    assert (done, errors) == (3, [])
    assert provider.calls == 1
    assert [row.title_zh for row in rows] == ["标题0", "标题1", "标题2"]
    assert [row.summary_zh for row in rows] == ["要点0", "要点1", "要点2"]


def test_missing_index_keeps_returned_ones(db):
    settings = Settings(_env_file=None, translate_batch_size=10)
    rows = _articles(db, 3)
    provider = ScriptedProvider(settings, lambda messages, call_no: _payload([0]))

    done, errors = translate_articles(db, rows, provider, settings)

    assert done == 1
    assert len(errors) == 2
    assert all("翻译失败" in message for message in errors)
    assert provider.calls == 1  # 缺项不触发减半重试
    assert rows[0].title_zh == "标题0"
    assert rows[1].title_zh is None and rows[2].title_zh is None


def test_duplicate_and_out_of_range_index_are_ignored(db):
    settings = Settings(_env_file=None, translate_batch_size=10)
    rows = _articles(db, 1)
    payload = json.dumps(
        [{"index": 0, "title_zh": "第一次", "summary_zh": "a"},
         {"index": 0, "title_zh": "第二次", "summary_zh": "b"},
         {"index": 9, "title_zh": "越界", "summary_zh": "c"}],
        ensure_ascii=False,
    )
    provider = ScriptedProvider(settings, lambda messages, call_no: payload)

    done, errors = translate_articles(db, rows, provider, settings)

    assert (done, errors) == (1, [])
    assert rows[0].title_zh == "第一次"


def test_invalid_output_splits_down_to_single(db):
    settings = Settings(_env_file=None, translate_batch_size=2)
    rows = _articles(db, 2)

    def script(messages, call_no):
        if call_no == 1:
            return "这不是 JSON"
        if call_no == 2:
            return _payload([0])
        return "这也不是 JSON"

    provider = ScriptedProvider(settings, script)

    done, errors = translate_articles(db, rows, provider, settings)

    assert provider.calls == 3  # 整批 → 拆两半
    assert done == 1
    assert len(errors) == 1
    assert rows[0].title_zh == "标题0"
    assert rows[1].title_zh is None


def test_provider_exception_does_not_raise(db):
    settings = Settings(_env_file=None, translate_batch_size=1)
    rows = _articles(db, 1)

    def script(messages, call_no):
        raise RuntimeError("boom")

    provider = ScriptedProvider(settings, script)

    done, errors = translate_articles(db, rows, provider, settings)

    assert done == 0
    assert len(errors) == 1


def test_chinese_source_written_without_model(db):
    settings = Settings(_env_file=None)
    rows = _articles(db, 2, lang="zh")
    provider = ScriptedProvider(settings, lambda messages, call_no: "不该被调用")

    done, errors = translate_articles(db, rows, provider, settings)

    assert (done, errors) == (2, [])
    assert provider.calls == 0
    assert rows[0].title_zh == "Title 0"


def test_existing_translation_is_not_overwritten(db):
    settings = Settings(_env_file=None)
    rows = _articles(db, 2)
    rows[0].title_zh = "已有译文"
    db.commit()
    provider = ScriptedProvider(settings, lambda messages, call_no: _payload([0]))

    done, errors = translate_articles(db, rows, provider, settings)

    assert (done, errors) == (1, [])
    assert provider.calls == 1
    assert rows[0].title_zh == "已有译文"
    assert rows[1].title_zh == "标题0"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest -q tests/test_translation.py`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.translation.translator'`

- [ ] **Step 3: 写实现**

新建 `backend/app/services/translation/translator.py`：

```python
"""按批翻译文章标题与摘要并落库。"""

from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import Article
from app.services.llm import ChatProvider
from app.services.translation.prompts import build_translation_prompt

TITLE_LIMIT = 500
SUMMARY_INPUT_CHARS = 1000


def translate_articles(db: Session, articles: list[Article], provider: ChatProvider,
                       settings: Settings) -> tuple[int, list[str]]:
    """给还没有译文的文章补 `title_zh` / `summary_zh`，返回（成功篇数，错误列表）。

    不抛异常：单篇失败只进错误列表，交给回填命令重试。
    """
    pending = [article for article in articles if not article.title_zh]
    if not pending:
        return 0, []
    native = [article for article in pending if article.lang == "zh"]
    _write_native(db, native)
    todo = [article for article in pending if article.lang != "zh"]
    done = len(native)
    errors: list[str] = []
    size = max(1, settings.translate_batch_size)
    for start in range(0, len(todo), size):
        batch_done, batch_errors = _run_batch(
            db, todo[start:start + size], provider, settings
        )
        done += batch_done
        errors.extend(batch_errors)
    return done, errors


def _write_native(db: Session, articles: list[Article]) -> None:
    """原文已是中文，直接落原文，不调模型。"""
    if not articles:
        return
    for article in articles:
        article.title_zh = article.title
        article.summary_zh = article.summary or None
    db.commit()


def _run_batch(db: Session, batch: list[Article], provider: ChatProvider,
               settings: Settings) -> tuple[int, list[str]]:
    """翻一批；整批不可用时对半拆开重试，收敛到单篇。"""
    try:
        raw = provider.complete(
            [{"role": "user", "content": build_translation_prompt(_prompt_items(batch))}],
            temperature=0.0,
            max_tokens=settings.llm_translate_max_tokens,
        )
        parsed = _parse_array(raw)
    except Exception as exc:  # noqa: BLE001 - 整批失败一律降级重试
        if len(batch) == 1:
            return 0, [f"文章 {batch[0].id} 翻译失败: {exc}"]
        half = len(batch) // 2
        done = 0
        errors: list[str] = []
        for part in (batch[:half], batch[half:]):
            part_done, part_errors = _run_batch(db, part, provider, settings)
            done += part_done
            errors.extend(part_errors)
        return done, errors
    return _apply(db, batch, parsed)


def _prompt_items(batch: list[Article]) -> list[tuple[int, str, str]]:
    return [
        (index, article.title, (article.summary or "")[:SUMMARY_INPUT_CHARS])
        for index, article in enumerate(batch)
    ]


def _parse_array(raw: str) -> list:
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    payload = json.loads(text)
    if not isinstance(payload, list):
        raise ValueError("翻译结果不是 JSON 数组")
    return payload


def _apply(db: Session, batch: list[Article], parsed: list) -> tuple[int, list[str]]:
    """按 index 对号入座；重复、越界、缺标题的条目一律丢弃。"""
    hits: dict[int, tuple[str, str | None]] = {}
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        index = entry.get("index")
        title_zh = str(entry.get("title_zh") or "").strip()
        if not isinstance(index, int) or index in hits:
            continue
        if not 0 <= index < len(batch) or not title_zh:
            continue
        summary_zh = str(entry.get("summary_zh") or "").strip() or None
        hits[index] = (title_zh[:TITLE_LIMIT], summary_zh)

    done = 0
    errors: list[str] = []
    for index, article in enumerate(batch):
        hit = hits.get(index)
        if hit is None:
            errors.append(f"文章 {article.id} 翻译失败: 模型未返回该条")
            continue
        article.title_zh, article.summary_zh = hit
        done += 1
    db.commit()
    return done, errors
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest -q tests/test_translation.py`
Expected: PASS（8 个用例）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/translation/translator.py backend/tests/test_translation.py
git commit -m "feat(backend): 批量翻译 service（index 校验 + 减半重试）"
```

---

## Task 5: 采集流程接入翻译

**Files:**
- Modify: `backend/app/services/flow.py`
- Test: `backend/tests/test_flow.py`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_flow.py` 末尾（该文件已 import `json`、`logs`、`articles`）：

```python
def test_collect_flow_translates_new_articles(db):
    import re

    from app.core.config import Settings

    task = _setup(db)
    settings = Settings(_env_file=None, extract_enabled=False)

    class TranslateProvider(ChatProvider):
        name = "translate"

        def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
            content = messages[-1]["content"]
            indexes = [int(hit) for hit in re.findall(r"^\[(\d+)\] 标题：", content, re.M)]
            return json.dumps(
                [{"index": i, "title_zh": f"标题{i}", "summary_zh": "要点"} for i in indexes],
                ensure_ascii=False,
            )

    result = run_task_flow(db, task, client=_feed_client(),
                           provider=TranslateProvider(settings), settings=settings)

    assert result["status"] == "success"
    rows = articles.list_articles(db)
    assert len(rows) == 2
    assert all(row.title_zh for row in rows)


def test_translate_failure_keeps_articles_and_marks_partial(db):
    from app.core.config import Settings

    class BoomTranslateProvider(FakeProvider):
        def complete(self, messages, temperature=0.2, max_tokens=4000) -> str:
            raise RuntimeError("boom")

    task = _setup(db)
    settings = Settings(_env_file=None, extract_enabled=False, translate_batch_size=1)

    result = run_task_flow(db, task, client=_feed_client(),
                           provider=BoomTranslateProvider(settings), settings=settings)

    assert result["new"] == 2                       # 采集本身成功
    assert result["status"] == "partial"            # 翻译失败不让整轮 failed
    assert logs.list_logs(db)[0].status == "partial"
    assert all(row.title_zh is None for row in articles.list_articles(db))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest -q tests/test_flow.py::test_collect_flow_translates_new_articles`
Expected: FAIL —— `assert all(row.title_zh for row in rows)` 失败（译文全是 `None`）

- [ ] **Step 3: 接进采集分支**

`backend/app/services/flow.py` 顶部 import 区，在 `from app.services.geo_tag import backfill_source_regions` 之后加：

```python
from app.services.translation import translator
```

在 `collect` 分支里，找到抽取循环之后的这一段：

```python
            if new_articles:
                try:
                    backfill_source_regions(db, new_articles)
```

在它之前插入翻译段：

```python
            if new_articles and settings.translate_enabled:
                try:
                    translate_provider = provider or get_provider(settings)
                    _, translate_errors = translator.translate_articles(
                        db, new_articles, translate_provider, settings
                    )
                    errors.extend(translate_errors)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"翻译失败: {exc}")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest -q tests/test_flow.py`
Expected: PASS（含新增 2 个用例；原有采集/分析用例不受影响）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/flow.py backend/tests/test_flow.py
git commit -m "feat(backend): 采集落库阶段批量生成中文标题与摘要"
```

---

## Task 6: 存量回填命令

**Files:**
- Create: `backend/scripts/backfill_translations.py`

- [ ] **Step 1: 写脚本**

新建 `backend/scripts/backfill_translations.py`：

```python
#!/usr/bin/env python
"""回填历史文章的标题与摘要译文（可反复执行，只补未完成的）。

用法（在 backend 目录下执行）：

    uv run python scripts/backfill_translations.py
    uv run python scripts/backfill_translations.py --limit 20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.database import make_engine, make_session_factory  # noqa: E402
from app.models.entities import Article  # noqa: E402
from app.services.llm import get_provider  # noqa: E402
from app.services.translation.translator import translate_articles  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="回填文章译文")
    parser.add_argument("--limit", type=int, default=0, help="最多处理多少篇，0 表示不限")
    args = parser.parse_args()

    settings = get_settings()
    engine = make_engine(settings.db_path)
    provider = get_provider(settings)
    session = make_session_factory(engine)()
    try:
        query = (session.query(Article)
                 .filter(Article.title_zh.is_(None))
                 .order_by(Article.id))
        rows = query.limit(args.limit).all() if args.limit else query.all()
        total = len(rows)
        print(f"待翻译 {total} 篇（批大小 {settings.translate_batch_size}）")
        done = failed = 0
        size = max(1, settings.translate_batch_size)
        for start in range(0, total, size):
            batch = rows[start:start + size]
            batch_done, batch_errors = translate_articles(session, batch, provider, settings)
            done += batch_done
            failed += len(batch_errors)
            print(f"  已处理 {start + len(batch)}/{total}｜成功 {done}｜失败 {failed}")
            for message in batch_errors:
                print(f"    - {message}")
        print(f"完成：成功 {done}，失败 {failed}")
        return 0 if failed == 0 else 1
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 验证脚本能跑（不调模型）**

先造一个空库验证启动路径与参数解析：

```bash
cd backend && DB_PATH=/tmp/aurora-backfill-smoke.db uv run python scripts/backfill_translations.py --help
```

Expected: 打印 `--limit` 的用法说明，退出码 0

- [ ] **Step 3: 提交**

```bash
git add backend/scripts/backfill_translations.py
git commit -m "feat(backend): 存量文章译文回填命令"
```

---

## Task 7: 接口带出译文

**Files:**
- Modify: `backend/app/api/serializers.py`
- Test: `backend/tests/test_serializers.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_serializers.py`：

```python
from app.api.serializers import article_out
from app.repositories import articles as articles_repo
from app.repositories import sources as sources_repo


def _one(db):
    src = sources_repo.create_source(db, name="S", url="https://example.com/feed",
                                     feed_type="rss", lang="en", categories=["politics"])
    articles_repo.insert_articles(db, [
        dict(source_id=src.id, category="politics", url="https://example.com/a",
             title="Title", summary="Summary", content_text="",
             published_at=None, lang="en", dedupe_hash="h1"),
    ])
    return articles_repo.list_articles(db)[0]


def test_article_out_carries_translations(db):
    article = _one(db)
    article.title_zh = "标题"
    article.summary_zh = "要点"
    db.commit()

    payload = article_out(article)

    assert payload["title_zh"] == "标题"
    assert payload["summary_zh"] == "要点"
    assert payload["title"] == "Title"  # 原文字段保持不变


def test_article_out_translation_is_null_when_missing(db):
    payload = article_out(_one(db))

    assert payload["title_zh"] is None
    assert payload["summary_zh"] is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest -q tests/test_serializers.py`
Expected: FAIL —— `KeyError: 'title_zh'`

- [ ] **Step 3: 加字段**

`backend/app/api/serializers.py` 的 `article_out` 里，把

```python
        "title": article.title,
        "url": article.url,
        "summary": article.summary,
```

改成

```python
        "title": article.title,
        "title_zh": article.title_zh,
        "url": article.url,
        "summary": article.summary,
        "summary_zh": article.summary_zh,
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest -q tests/test_serializers.py`
Expected: PASS

- [ ] **Step 5: 跑全量后端测试**

Run: `cd backend && uv run pytest -q`
Expected: PASS（129 + 新增用例）

- [ ] **Step 6: 提交**

```bash
git add backend/app/api/serializers.py backend/tests/test_serializers.py
git commit -m "feat(backend): 文章接口带出中文标题与摘要"
```

---

## Task 8: 前端类型与展示纯函数

**Files:**
- Modify: `frontend/src/api/types.ts`
- Create: `frontend/src/utils/article.ts`
- Create: `frontend/src/utils/article.test.ts`

- [ ] **Step 1: 写失败测试**

新建 `frontend/src/utils/article.test.ts`：

```ts
import { describe, expect, it } from "vitest";

import { displaySummary, displayTitle } from "./article";

describe("displayTitle", () => {
  it("prefers the translation", () => {
    expect(displayTitle({ title: "Fed hikes rates", title_zh: "美联储加息" })).toBe("美联储加息");
  });

  it("falls back to the original when missing or blank", () => {
    expect(displayTitle({ title: "Fed hikes rates", title_zh: null })).toBe("Fed hikes rates");
    expect(displayTitle({ title: "Fed hikes rates", title_zh: "   " })).toBe("Fed hikes rates");
  });
});

describe("displaySummary", () => {
  it("prefers the translation", () => {
    expect(displaySummary({ summary: "original", summary_zh: "中文要点" })).toBe("中文要点");
  });

  it("falls back to the original, then to an empty string", () => {
    expect(displaySummary({ summary: "original", summary_zh: null })).toBe("original");
    expect(displaySummary({ summary: null, summary_zh: null })).toBe("");
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npm test`
Expected: FAIL —— `Failed to resolve import "./article"`

- [ ] **Step 3: 加类型**

`frontend/src/api/types.ts` 的 `ArticleItem` 里，把

```ts
  title: string;
  url: string;
  summary: string | null;
```

改成

```ts
  title: string;
  title_zh: string | null;
  url: string;
  summary: string | null;
  summary_zh: string | null;
```

- [ ] **Step 4: 写纯函数**

新建 `frontend/src/utils/article.ts`：

```ts
import type { ArticleItem } from "../api/types";

/** 列表标题：有译文用译文，译文缺失或空白时回落原文。 */
export function displayTitle(item: Pick<ArticleItem, "title" | "title_zh">): string {
  const zh = item.title_zh?.trim();
  return zh || item.title;
}

/** 列表摘要：同上；两边都没有时返回空串，调用方据此不渲染整行。 */
export function displaySummary(
  item: Pick<ArticleItem, "summary" | "summary_zh">,
): string {
  const zh = item.summary_zh?.trim();
  return zh || (item.summary ?? "").trim();
}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd frontend && npm test && npm run typecheck`
Expected: PASS（26 + 4 = 30 个用例；`typecheck` 无错）

- [ ] **Step 6: 提交**

```bash
git add frontend/src/api/types.ts frontend/src/utils/article.ts frontend/src/utils/article.test.ts
git commit -m "feat(frontend): 文章译文类型与展示回落纯函数"
```

---

## Task 9: 地区面板滚动约束与中文展示

**Files:**
- Modify: `frontend/src/constants/mapBoard.ts`
- Modify: `frontend/src/components/map/RegionPanel.tsx`

- [ ] **Step 1: 加常量**

`frontend/src/constants/mapBoard.ts` 的 `MAP_BOARD_STYLE` 里，在 `stripPadding: 10,` 之后插入：

```ts
  // 地区面板列表容器：与地图卡片（height 520）对齐，超出时容器内滚动
  listMaxHeight: 440,
  listMinHeight: 240,
```

在 `MAP_BOARD_TEXT` 里，在 `regionEmpty` 之后插入：

```ts
  summaryLines: 2,
```

- [ ] **Step 2: 改 RegionPanel**

`frontend/src/components/map/RegionPanel.tsx` 做四处改动。

(1) import 区：把

```tsx
import { Button, Card, List, Space, Tag } from "antd";
```

改成

```tsx
import { Button, Card, List, Space, Tag, Typography } from "antd";
```

并在 `import { formatDateTime } from "../../utils/format";` 之后加：

```tsx
import { displaySummary, displayTitle } from "../../utils/article";
```

(2) 在组件定义之前插入滚动容器（两个状态共用，保证面板高度稳定）：

```tsx
/** 固定高度的滚动容器：列表超出时在容器内滚，页面不被撑长。 */
function ScrollBody({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        maxHeight: MAP_BOARD_STYLE.listMaxHeight,
        minHeight: MAP_BOARD_STYLE.listMinHeight,
        overflowY: "auto",
      }}
    >
      {children}
    </div>
  );
}
```

(3) 未选中状态的卡片正文：把

```tsx
        {regions.length === 0 ? (
          <EmptyHint text={GEO_TEXT.empty} compact />
        ) : (
          <List
            size="small"
            dataSource={regions.slice(0, 12)}
```

改成

```tsx
        {regions.length === 0 ? (
          <ScrollBody>
            <EmptyHint text={GEO_TEXT.empty} compact />
          </ScrollBody>
        ) : (
          <List
            size="small"
            dataSource={regions.slice(0, 12)}
```

(4) 选中状态的列表：把 error/empty/List 三段整体包进 `ScrollBody`，并把列表条目换成中文标题 + 中文摘要：

```tsx
      <ScrollBody>
        {detail.error ? (
          <EmptyHint text={MAP_BOARD_TEXT.regionError(detail.error)} compact />
        ) : items.length === 0 ? (
          <EmptyHint text={MAP_BOARD_TEXT.regionEmpty} compact />
        ) : (
          <List
            size="small"
            dataSource={items}
            renderItem={(item) => {
              const meta = CATEGORY_MAP[item.category as CategoryKey];
              const summary = displaySummary(item);
              return (
                <List.Item>
                  <List.Item.Meta
                    title={
                      <a href={item.url} target="_blank" rel="noreferrer">
                        {displayTitle(item)}
                      </a>
                    }
                    description={
                      <div>
                        {summary ? (
                          <Typography.Paragraph
                            type="secondary"
                            style={{ marginBottom: 4, fontSize: 12 }}
                            ellipsis={{ rows: MAP_BOARD_TEXT.summaryLines }}
                          >
                            {summary}
                          </Typography.Paragraph>
                        ) : null}
                        <span className="aurora-muted">
                          <Tag color={meta?.color}>{meta?.label ?? item.category}</Tag>
                          {item.source_name ?? MAP_BOARD_TEXT.unknownSource} ·{" "}
                          {formatDateTime(item.published_at ?? item.fetched_at)}
                        </span>
                      </div>
                    }
                  />
                </List.Item>
              );
            }}
          />
        )}
      </ScrollBody>
```

- [ ] **Step 3: 跑校验**

Run: `cd frontend && npm test && npm run typecheck && npm run build`
Expected: 三项都通过；`build` 只有既有的 chunk 体积警告

- [ ] **Step 4: 本地肉眼验收**

```bash
cd backend && DATABASE_URL= DB_PATH=/tmp/aurora-ui-check.db SCHEDULER_ENABLED=false uv run uvicorn app.main:app --port 8300 --workers 1
cd frontend && npx vite --port 5300
```

打开 `http://127.0.0.1:5300/`，确认：选中一个国家后右栏高度不超过地图卡片、列表在容器内滚动、页面不被撑长、条目显示中文标题与摘要（库里若都是旧数据则回落英文，属预期）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/constants/mapBoard.ts frontend/src/components/map/RegionPanel.tsx
git commit -m "feat(frontend): 地区列表容器内滚动并展示中文标题摘要"
```

---

## Task 10: 文档、全量验收与上线

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 补 README**

`README.md` 的「主要 API」之前插入一节：

```markdown
## 中文译文

文章标题与摘要在采集落库阶段批量翻译（`translate_enabled`，批大小 `translate_batch_size`），
写入 `articles.title_zh` / `articles.summary_zh`；缺译文时前端回落显示原文。
存量文章用下面这条命令补齐，可反复执行：

```bash
cd backend && uv run python scripts/backfill_translations.py
```

老库启动时由 `ensure_schema` 自动补上这两列，不需要手工迁移。
```

- [ ] **Step 2: 全量验收**

Run:
```bash
cd backend && uv run pytest -q
cd ../frontend && npm test && npm run typecheck && npm run build
```
Expected: 后端全部通过；前端 30 个用例通过、类型检查无错、构建成功

- [ ] **Step 3: 提交**

```bash
git add README.md
git commit -m "docs: 中文译文的生成与回填说明"
```

- [ ] **Step 4: 部署并回填**

```bash
cd frontend && npm run build
# 打包上传（沿用上次的方式：tar + scp 到 /opt/aurora，然后 uv sync）
# 服务器上：
systemctl restart aurora          # ensure_schema 自动补两列
cd /opt/aurora/backend && .venv/bin/python scripts/backfill_translations.py
curl -u aurora:<口令> http://8.133.207.129:3000/api/regions/gb/articles?window=24h | head -c 400
```
Expected: 补列成功、回填打印成功篇数、接口返回 `title_zh` 非空

---

## 完成标准

- 后端新增译文列并可由老库自动补列，`uv run pytest -q` 全绿
- 翻译在采集分支生效，整批失败能收敛到单篇，失败只让状态变 `partial`
- `article_out` 返回 `title_zh` / `summary_zh`
- 前端点国家后列表在容器内滚动、面板与地图等高、显示中文标题与摘要、缺译文回落原文
- 服务器已重启（补列）并跑完回填，`/api/regions/gb/articles` 返回中文
