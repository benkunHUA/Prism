# Aurora 世界地图看板设计（增量规范）

- 日期：2026-10-12
- 状态：设计已获用户确认（brainstorming 完成）
- 关系：把现有 `/` 仪表盘升级为「世界地图看板」；不改动四板块页、源管理、任务管理与待确认审核
- 前置：`2026-09-07-aurora-info-analysis-design.md`、`2026-09-08-aurora-category-differentiation-design.md`

## 1. 背景与目标

现状看板是 4 张统计卡 + 4 张板块入口卡，只能回答"今天有多少条"，回答不了"今天哪里最热、都是哪类新闻"。同时 `articles` 表没有任何地理字段，只有 `timeline_events.region` 与 `macro_indicators.region` 两个自由文本列，且只覆盖已抽取、已审核的条目 —— 直接拿来做地图会长期点很稀。

目标：进入看板即世界地图，**一眼看出各地区的新闻热度，并看出每个地区的新闻构成（政治/经济/金融/军事）**，点击地区就地看该地区新闻列表，再点标题看详情，全程不离开地图。

成功标准：

- 打开 `/` 3 秒内看出今天最热的 3 个地区，以及各自以哪类新闻为主
- 点任一地区 ≤1 次点击看到该地区近 24 小时新闻列表
- 未被地理标注的文章有明确计数入口，不静默丢弃
- 地图与图例在**无外网**环境可用（不依赖在线瓦片）

## 2. 已确认决策摘要

| 议题 | 决策 | 理由 |
| --- | --- | --- |
| 位置数据来源 | 文章级 LLM 打标为主 + 源地区兜底（混合） | 覆盖全量文章，且打标可并入现有抽取，零额外调用 |
| 地图表达 | 双层：底层国家填色=热度，上层彩点=类别 | 两个诉求各由一层回答，点压叠时填色仍能说明热度 |
| 页面骨架 | 单页闭环：地图 + 右侧面板就地切换（地区榜 ↔ 地区新闻列表） | 空间上下文不丢，"哪里多"和"发生了什么"同屏 |
| 地区粒度 | 国家级词表 + 少量热点区常量（台海/加沙/南海/红海…） | 映射稳定，且非国家热点有处可落 |
| 时间窗 | 默认近 24 小时，可切 7 天 / 30 天 | 兼顾"今天哪儿热"与周末点稀的问题 |
| 地图技术 | ECharts（按需引入 geo + scatter）+ 本地 world GeoJSON | 离线可用，填色与散点一个库搞定 |

## 3. 地区词表与语义

新增 `backend/app/core/geo.py`（纯数据 + 纯函数，不依赖 ORM）：

- `COUNTRIES`：`code`（ISO 3166-1 alpha-2 小写）、`name_zh`、`aliases`（中文/英文/常见简称）、`lng`、`lat`（预置质心，不从几何现算）。收录范围以现有采集源实际覆盖为准，先覆盖主要国家，后续按需增补。
- `HOTSPOTS`：`code`（如 `tw_strait`、`gaza`、`south_china_sea`、`red_sea`）、`name_zh`、`aliases`、`lng`、`lat`。
- `normalize_region(text) -> str | None`：去空白与常见后缀后，先精确匹配别名，再匹配包含关系；命中返回 `code`，未命中返回 `None`。
- `REGION_NAMES`：`code -> name_zh` 反查表，供接口与前端图例使用。

两条语义规则：

1. **热点区是一等地区，不并入所属国家**。报道"台海"只计 `tw_strait`，不计入任何国家；避免把地区性事件错误归到某个国家的新闻量上。
2. **归一失败的名字丢弃，只写日志，不落库**，也不做模糊猜测（避免污染热度）。

## 4. 数据模型变更（新增 1 张表，改 1 张现有表）

开发期数据库直接重建（与既有约定一致，不写迁移脚本）。

### 4.1 新增 `article_regions`

文章与地区的多对多关联，是一期唯一的数据来源：

`id, article_id(FK articles, ondelete CASCADE), region_code(String(32)), source(String(10): llm|source), created_at`

- 唯一约束：`(article_id, region_code)`
- 索引：`region_code`
- `source` 区分打标来源，便于后续评估打标质量；二期新增 `event` 取值表示事件层精修

### 4.2 `sources` 增加 `region` 列

`region: String(32) default ""`，存 `region_code`，供兜底路径使用。源管理页加一个地区下拉（可选，留空即不兜底）。

### 4.3 抽取 schema 增加 `regions`

`backend/app/services/extraction/schemas.py` 四个板块模型各加一个字段：

`regions: list[str] = []` —— LLM 返回中文/英文地区名，服务端用 `normalize_region()` 归一化后落库。

`prompts.py` 的 `build_extraction_prompt` 增加一句说明：地区名取"新闻发生地"，可多个；无明确发生地时留空；优先使用词表内的国家名与热点区名。

## 5. 打标管线（并入现有采集流程）

落点在 `backend/app/services/flow.py` 的 `collect` 分支，不新增任务类型、不新增 LLM 调用：

1. **打标**：采集入库后，现有 `extract_article()` 已对每篇新文章跑一次板块抽取；本次在其内部增加 `_write_regions()`，把 `parsed.regions` 归一化后写入 `article_regions`（`source='llm'`）。
2. **兜底**：抽取循环结束后，在 `flow.py` 里对本次全部新文章统一跑一次 `_backfill_regions()` —— 凡是当前没有任何 `article_regions` 记录的文章（覆盖 `extract_enabled=False`、抽取失败、LLM 未给出地区三种情况），若其来源源配置了 `sources.region` 就补一条 `source='source'` 记录；源也没配则保持未标注。
3. 抽取与兜底失败都不阻断采集流程，错误照旧进 `run_logs`（沿用现有降级策略）。

未标注文章 = `articles` 中在时间窗内、但不存在任何 `article_regions` 记录的行，由聚合接口统计为 `untagged`。

## 6. API 变更（增量）

### 6.1 `GET /api/dashboard/geo?window=24h|7d|30d`

返回直接可渲染的聚合结果，前端不做二次聚合：

```
{
  "window": "24h",
  "window_start": "...",
  "total": 128,
  "untagged": 9,
  "regions": [
    {"code": "il", "name": "以色列", "lng": ..., "lat": ..., "count": 12,
     "by_category": {"politics": 3, "military": 6, "economy": 2, "finance": 1}}
  ]
}
```

- 口径：`count` = 该地区在该时间窗内关联的文章数（一篇文章多地区各计一次）；`by_category` 按 `articles.category` 分组。
- 时间窗按 `articles.fetched_at` 过滤（与现有统计口径一致）。
- 词表内每个地区都带坐标，聚合结果无需处理缺坐标情况。

### 6.2 `GET /api/regions/{code}/articles?window=24h&category=<cat>&limit=30`

地区新闻列表，供右栏面板使用。现有 `GET /api/categories/{category}/articles` 强制要求板块，无法表达"某地区下全部板块"，因此新增地区维度端点；返回结构与现有文章列表接口一致（复用 `_out()` 与 `_summary` 风格）。

- `category` 省略时返回该地区全部板块文章
- 仓储层新增 `list_articles_by_region(db, region_code, since, category=None, limit, offset)`

## 7. 前端结构与交互

### 7.1 页面归属

`MapBoardPage` 替换现 `DashboardPage` 占用的 `/` 路由。**原仪表盘信息不丢**：地图上方保留 `StatCards` 一行（今日文章 / 今日分析 / 源健康 / 下次任务），并新增 `CategoryStrip` 紧凑条承接原 4 张板块卡的信息 —— 每个板块一个 chip（板块色 + 板块名 + 近 24 小时条数），chip 的 tooltip 显示最新日报标题，点击进入对应板块页。`DashboardPage.tsx` 删除。

### 7.2 组件拆分（单文件 ≤300 行）

| 文件 | 职责 |
| --- | --- |
| `frontend/src/pages/MapBoardPage.tsx` | 组合布局与数据拉取，不含渲染细节 |
| `frontend/src/components/map/WorldMap.tsx` | ECharts 实例封装：双层 option 生成、点击事件、resize |
| `frontend/src/components/map/RegionPanel.tsx` | 右栏两态（地区榜 ↔ 地区新闻列表）与切换 |
| `frontend/src/components/map/MapLegend.tsx` | 四板块图例 + 时间窗切换 + 未定位计数 |
| `frontend/src/components/map/CategoryStrip.tsx` | 四板块 chip 条（近 24h 条数 + 最新日报 tooltip + 跳转） |
| `frontend/src/constants/geo.ts` | 时间窗选项、图例文案、`window` 参数映射等常量 |
| `frontend/src/utils/geo.ts` | 纯函数：分位数配色分档、区域聚合选择器（单测对象） |
| `frontend/src/api/*` | 新增 `geo(window)` 与 `regionArticles(code, {window, category})` 端点与类型 |

底图数据 `frontend/src/assets/world.geo.json`：取自 Natural Earth 1:110m 国家边界的简化版（提交进仓库，体积目标 <200KB），仅用于填色与命中判定，散点坐标一律由 `geo.py` 词表提供，不依赖在线瓦片或远程地图服务。

### 7.3 交互规则

- **双层渲染**：底层 `geo` 系列按国家填色（无数据国家用最浅一档，不隐藏国土）；上层 `scatter` 系列按「地区 × 板块」展开成点 —— 同一地区最多 4 个点，颜色取板块色，坐标在词表坐标上做固定小偏移（约 ±0.7°）避免完全重叠。**不按文章逐篇打点**：同一地区所有文章坐标相同，逐篇点会完全压叠，视觉上等价于一个点，只会白烧渲染性能。
- **热度分档用分位数而非线性**，避免单个超热地区把其余国家压成一片浅色；档位与算法放 `utils/geo.ts`。
- **点击**：点国家或热点区 → 右栏从「地区榜」切到「{地区名} · 近 {窗口}」新闻列表；列表项沿用现有 `ArticleList` 的做法（标题外链原文，`target=_blank`，不新增详情抽屉）；列表顶部「← 返回地区榜」。
- **图例即筛选**：点击图例里的板块色 → 只显示该类散点（填色层不变）。
- **空态**：无任何地区数据时，地图仅显示底图 + 提示"暂无地理标注数据，请先执行采集任务"；`untagged > 0` 时在图例旁显示「未定位 N 条」。

## 8. 保留不变

四板块页（政治/经济/金融/军事）、源管理、任务管理、待确认审核抽屉、手动采集按钮、行情快照与报告生成全链路均不修改。新增列与表对既有查询无影响。

## 9. 测试策略

- 后端：`geo.py` 归一化单测（中文别名、英文名、热点区、未命中、空串）；`article_regions` 去重与级联删除；`/api/dashboard/geo` 的窗口过滤、`by_category` 分组、`untagged` 计算。
- 前端：`utils/geo.ts` 纯函数单测（分位数分档、聚合选择器）；`npm test` 与 `npm run build`（含类型检查）必须通过。

## 10. 迭代计划

- 一期：词表 → 抽取加 `regions` 与落库 → 兜底与源地区列 → 聚合接口 → 地图组件 → 右栏与图例。
- 二期（不在本次范围）：用 `timeline_events.region` / `macro_indicators.region` 做事件层精修（`source='event'`）、地区详情页、时间轴回放。

## 11. 风险与应对

| 风险 | 应对 |
| --- | --- |
| LLM 打标误判（把报道机构所在地当发生地） | prompt 明确"新闻发生地"；`source` 字段可回溯；归一失败直接丢弃 |
| 地区名不在词表 → 点落在图外 | `normalize_region` 未命中即丢弃并写日志；词表按采集源实际覆盖滚动增补 |
| 一篇文章涉及多地区导致热度虚高 | `count` 按去重后的 `(article_id, region_code)` 计算，且多地区各计一次是刻意选择（反映"相关热度"） |
| ECharts + GeoJSON 体积 | 按需引入 `GeoComponent`/`MapChart`/`ScatterChart`；GeoJSON 用简化边界，构建后校验产物体积 |
| 现有点位数据太稀导致地图难看 | 兜底路径保证全量文章至少有源级标签；`untagged` 计数暴露真实缺口 |
