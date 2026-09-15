# Aurora 四板块差异化设计（增量规范）

- 日期：2026-09-08
- 状态：设计已获用户确认（brainstorming 完成）
- 关系：对 `2026-09-07-aurora-info-analysis-design.md` 的内容层做差异化升级；数据组织采用方案 C（事件共用底表 + 专属表）

## 1. 背景与目标

原系统把四大板块做成统一形态（快讯 + 通用五段式每日分析）。用户确认需要改为**四个独立的板块产品**：各自有固定栏目、结构化数据、专属每日产出与差异化页面。结构化条目由 LLM 从白名单新闻提取，采用**分级可信**：客观事实自动入库，高幻觉风险内容先进“待确认”队列人工复核。

成功标准：

- 军事板块可回答“有哪些新武器/装备动态、冲突推进到哪一步”
- 政治板块可回答“重大事件脉络 + 各方在某议题上的立场变化”
- 经济板块可回答“最新指标是超预期还是不及、政策往哪个方向走”
- 金融板块可回答“市场涨了什么/跌了什么、为什么、风险信号在哪”
- 每条结构化记录可回溯原文，待确认条目有明确的审核入口

## 2. 板块定位总表

| 板块 | 定位 | 固定栏目 | 结构化对象 | 每日产出 |
| --- | --- | --- | --- | --- |
| 政治 | 谁在做决定·为什么·下一步 | 选举与组阁 / 立法投票 / 外交与峰会 / 制裁与条约 / 安全战略声明 | 政治事件时间线 + 议题立场追踪 | 政情综述 |
| 军事 | 谁有了什么新武器·仗打到哪一步 | 武器装备动态 / 冲突与战事进展 /（快讯）演习·部署·军贸·防务预算 | 武器档案 + 冲突事件时间线 | 军事态势简报 |
| 经济 | 数据说明现状·政策指明方向 | 宏观数据发布 / 央行与财政政策 / 贸易与产业政策 / 机构预测调整 | 宏观指标点 + 政策事件时间线 | 宏观与政策简报 |
| 金融 | 价格怎么变·为什么变·风险在哪 | 主要市场表现 / 资金与流动性 / 公司大事件 / 监管动向 | 市场快照 + 市场事件时间线 | 市场复盘 |

## 3. 数据模型变更（新增 5 张表，不动现有 8 张）

开发期数据库直接重建（删除旧 `data/aurora.db` 后由 create_all 重建）；生产路径尚无存量数据迁移需求。

### 3.1 timeline_events · 事件共用底表

政治、军事冲突、经济政策、金融市场四类事件共用：

`id, category(politics|military|economy|finance), subtype, actor, region, occurred_at, summary, importance(high|medium|low), verification_status(confirmed|draft|rejected), confidence, article_id(FK, nullable), group_key, created_at, updated_at`

索引：`(category, occurred_at desc)`、`verification_status`。

subtype 收敛词表：

| category | subtype |
| --- | --- |
| politics | 选举/组阁、立法与投票、外交与峰会、制裁与出口管制、条约与协议、安全战略声明 |
| military | 冲突进展、停火与和谈、军事行动、袭击与损失 |
| economy | 货币政策、财政政策、贸易政策、产业政策、监管与改革 |
| finance | 市场异动、融资/IPO/并购、监管动态、公司重大事件、资金与流动性 |

`group_key` 用于把同一战线/同一事件的多次进展聚合展示（例如 `conflict:ukraine-east`），为空表示一次性事件。

### 3.2 military_weapons · 武器档案

`id, name, original_name, origin, weapon_type, params_text, lifecycle_status(研发|测试|列装|部署|出口|退役), merge_key, verification_status, confidence, first_seen_at, last_seen_at, article_id, created_at, updated_at`

- `merge_key` = 规范化（名称+国别）哈希；同 key 已有记录则更新参数与状态，不重复插入
- `params_text` 为模型提取的要点文本（Markdown），默认进草稿

### 3.3 macro_indicators · 宏观指标点

`id, indicator, region, period, value, unit, previous, forecast, released_at, merge_key, verification_status, confidence, article_id, created_at, updated_at`

- `merge_key` = 规范化（指标+地区+周期）；发布后若修正则覆盖数值并保留 updated_at
- `previous/forecast` 可空；`value` 为数值，单位放 `unit`（如 `%`、`万`）
- 判定“好于/不及预期”由前端按数值比较展示，不入库

### 3.4 market_snapshots · 市场快照

`id, asset_code, asset_name, asset_class(index|rate|fx|commodity|volatility|crypto), price, change_pct, captured_at, batch_id, source, created_at`

- 来源为**行情数据模块**（非 LLM），Provider 可插拔；默认免费源 Stooq CSV，失败静默降级
- `batch_id` 标识同一轮抓取批次，用于对比“较上轮”

### 3.5 stance_topics · 议题立场追踪

`id, topic(对华|俄乌|中东|台海|贸易|科技管制|气候|能源), actor, stance_text, tone, stated_at, verification_status, confidence, article_id, created_at`

- 每次新表态**追加一行**保留历史；前端按 `(topic, actor)` 取最新一条展示，可展开历史
- `tone` 为人工可读标签（如 趋严/缓和/支持/反对/中性/未定），默认进草稿

### 3.6 既有表语义

- `articles` 不变：仍是原文底座，所有结构化表通过 `article_id` 溯源
- `analyses` 不变：`kind=brief|daily` 继续使用；daily 的文章结构、标题与提示词按 `category` 分四套模板（见 §6）
- `run_logs` 增加用途：结构化提取与行情抓取也在任务流内记日志

## 4. 结构化提取与校验管线

触发时机：每轮采集入库后、生成快讯前，对新增原文逐篇执行板块提取。

1. 按板块 schema 组装提示词，要求 LLM 只输出 JSON
2. Pydantic 强校验：subtype/日期/数值/枚举；失败整条丢弃并写日志
3. 归并：武器=名称+国别、指标=指标+地区+周期、立场=议题+主体、事件=类型+主体+日期/group_key
4. 分级可信：
   - **自动确认**：选举与投票结果、利率与政策决定、数据发布数值、停火与协议声明、并购/IPO 公告、峰会举行（时间地点明确的客观事实）
   - **进草稿**：武器参数与状态判断、冲突伤亡数字与双方说法、议题立场定性、事件影响归因、importance 分级
5. 每条记录写入时带 `verification_status` 与 `confidence`

“待确认”队列 = 五张表中 `verification_status=draft` 的并集；审核动作 confirm / edit / reject 均记录到对应行。

## 5. 行情快照模块

- `marketdata` 服务：Provider 接口 `fetch(symbols) -> (rows, errors)`；默认 `EastmoneyProvider`（东方财富批量接口，国内可达：标普 500 `100.SPX`、道指 `100.DJIA`、纳指 `100.NDX`、美元指数 `100.UDI`、伦敦金 `101.GC00Y`、纽约原油 `101.CL00Y` 等），`StooqCsvProvider` 保留为备选
- 轮询节奏：随每轮采集执行；失败单资产跳过、整轮不失败；`run_logs` 记成功/失败数
- `MARKET_SYMBOLS` 默认留空（不主动联网）；需要时在 `.env` 中按 `class|名称=代码` 逗号分隔启用
- 实施期实测（2026-09-15）：Stooq `/q/l/` 接口已 404、Yahoo chart 在当前网络返回非 JSON；东方财富首次探测成功，连续快速请求会被断连，因此实现为**单次批量请求 + 失败降级**，并把标的清单做成可配置

## 6. 每日报告模板（四套）

`analyses(kind=daily)` 的正文结构按板块由对应提示词产出，标题示例：

- 政治：`政治每日综述 · 2026-09-08`
  - 章节：今日要闻 → 事件脉络（按时间线）→ 议题立场变化 → 下一步看点
- 军事：`军事态势简报 · 2026-09-08`
  - 章节：态势要点 → 新武器/装备动态（档案+参数）→ 冲突进展（按战线）→ 演习/军贸/防务快讯 → 态势展望
- 经济：`宏观与政策简报 · 2026-09-08`
  - 章节：数据要点（数值 vs 预期 vs 前值）→ 政策动作与影响对象 → 机构预测调整 → 传导提示
- 金融：`市场复盘 · 2026-09-08`
  - 章节：资产表现（快照对比）→ 驱动事件归因 → 资金与风险信号 → 明日关注

快讯（brief）仍为 4~6 小时一版的板块要点；结构化条目在板块页独立展示，不再混在快讯正文里。

## 7. API 变更（增量）

- `GET /api/categories/{cat}/timeline`（带 subtype/importance 过滤）
- `GET /api/military/weapons`（带 lifecycle_status 过滤，含最近更新排序）
- `GET /api/economy/indicators`（带 indicator/region/period 过滤）
- `GET /api/politics/stances?topic=&actor=`（含历史展开）
- `GET /api/finance/snapshots?asset_class=&batch_id=`（含 batch 间对比所需字段）
- `GET /api/moderations?category=&type=`（草稿并集）
- `PATCH /api/moderations/{type}/{id}`（type ∈ timeline|weapon|indicator|stance；body: action=confirm|edit|reject，edit 带更新字段）
- `POST /api/finance/snapshots/refresh`（手动触发一轮快照）

## 8. 前端页面变化（并入计划 B）

- 政治页：事件时间线 + 议题立场卡片 + 政情综述
- 军事页：武器卡片网格 + 按战线冲突时间线 + 态势简报 + 顶部统计
- 经济页：指标表（vs 前值/预期着色）+ 政策事件流 + 简报
- 金融页：市场快照表（涨跌配色）+ 事件归因 + 复盘
- 全局顶栏“待确认 N”徽标 → 审核抽屉（确认/编辑/丢弃），按板块过滤
- 仪表盘：四板块卡片各自展示“今日报告 + 板块特色摘要”（指标/武器/事件数等）

## 9. 保留不变

- 白名单源、采集、去重、健康停用机制
- LLM 可插拔 Provider（默认 DeepSeek）
- SQLite(WAL) + APScheduler + FastAPI 单进程架构
- 源管理页、任务管理页、手动执行、运行日志

## 10. 测试策略增量

- 提取：每个板块用固定样例文章 + Fake LLM 输出 JSON，校验解析/校验失败/归并/分级结果
- 归并：同武器二次出现更新不重复；同指标同周期修正覆盖；立场追加历史
- 行情：本地 fixture CSV + MockTransport 验证 snapshot Provider 与失败降级
- 审核 API：草稿确认/编辑/拒绝后状态变化与可见性
- 报告模板：Fake LLM 输出验证四个板块的标题与章节提示词被正确选用

## 11. 迭代计划

- **R1 后端数据与提取**：5 张新表 + 提取管线（schema/提示词/校验/归并/分级）+ 审核 API + 行情快照 Provider
- **R2 板块产物**：四套每日报告模板与提示词接入 flow
- **R3 前端重构**：四个差异化板块页 + 仪表盘调整 + 审核界面（与计划 B 合并执行）

每轮独立可测、频繁提交，完成后合并回 main 并推送 Prism。

## 12. 风险与应对

- **提取幻觉**：分级草稿 + 人工确认 + 原文回溯；武器参数与立场定性默认不自动展示
- **行情免费源不稳定**：Provider 可替换 + 单资产失败降级；实测 Stooq/Yahoo 不可用后默认改用东方财富批量接口；后续可换付费/自建源或加代理
- **人工审核成本**：草稿范围收窄到明确清单（§4），日常确认操作设计为一键批量
- **范围膨胀**：subtype 词表与栏目在第一版锁死，后续以“新增 subtype”而非“新增对象模型”扩展
