# Aurora 地区新闻列表中文化与滚动约束（增量规范）

- 日期：2026-10-13
- 状态：设计已获用户确认（brainstorming 完成）
- 关系：只改看板右栏地区新闻列表；不改动四板块页、抽取管线语义、源管理、任务管理
- 前置：`2026-10-12-aurora-world-map-dashboard-design.md`

## 1. 背景与目标

现在点看板上任一国家，右栏列表把 30 条原文标题全部铺开，面板被拉到 1500px 以上，而地图只有 520px —— 两者错位，整页被拖长；同时列表全是英文原文标题，中文读者要逐条读英文。

目标：点国家后，**列表在自己的容器内滚动**（面板高度与地图对齐），**条目显示中文标题与中文摘要**。

成功标准：

- 选中地区后右栏高度不超过地图卡片高度，页面不出现额外纵向滚动
- 后端不可用或没有译文时列表仍可用，回落显示原文标题，不出现空白条目
- 译文在采集落库阶段产生，列表接口一次返回即可渲染，前端不做二次请求

## 2. 已确认决策摘要

| 议题 | 决策 | 理由 |
| --- | --- | --- |
| 翻译范围 | 标题 + 摘要；不翻正文 | 列表只展示这两项，正文不在界面上出现过 |
| 翻译时机 | 采集落库阶段写库（`title_zh` / `summary_zh`） | 列表秒出，无按需延迟，一次付费一次 |
| 翻译方式 | 复用现有 DeepSeek（`ChatProvider`） | Google 在阿里云不可达；百度/有道要另配 key 另计费；本地 MT 在 2 核 1.6G 机器上不划算且质量不足 |
| 与抽取的关系 | 独立翻译步骤，不并入抽取调用 | 抽取失败/关闭也能有中文；存量回填复用同一 service，不重跑抽取（否则会连带重写事件时间线） |
| 摘要形态 | 中文要点（≤120 字），非逐字翻译 | 原 summary 最长 2000 字符，逐字翻既贵又放不进两行列表 |
| 缺译文表现 | 前端回落原文标题/摘要 | 翻译失败不该让列表出现空条目 |

## 3. 数据模型变更（改 1 张现有表）

`articles` 增加两列，均可空，不改现有字段语义：

- `title_zh: String(500) | None`
- `summary_zh: Text | None`（默认空串亦可，取值时按空处理）

迁移方式：不加迁移脚本，沿用 `backend/app/core/schema.py` 的 `ensure_schema` —— 启动时 `create_all` 之后比对列并 `ALTER TABLE ADD COLUMN`，幂等。新增列可空，不会给存量行填错值。

## 4. 翻译服务

新增 `app/services/translation/`：

- `prompts.py`：翻译提示词与文案常量（按 AGENTS.md「配置与文案外置」）
- `translator.py`：`translate_article(db, article, provider, settings) -> bool`

行为约定：

1. 输入只用 `article.title` 与 `article.summary`（截断到 `max_analysis_input_chars` 级别的上限），不读 `content_text`，避免正文带来额外 token。
2. 要求模型返回 JSON `{"title_zh": "...", "summary_zh": "..."}`，失败即放弃本篇（不写库、不抛异常给调用方），由回填命令兜底重试。
3. 已有 `title_zh` 的文章直接跳过，保证重复调用幂等。
4. 输出为空或被截断（复用 `LLMResponseError` 判定）时不写库。
5. 原文已是中文（`article.lang == "zh"`）时跳过翻译，直接写入 `title_zh = title`、`summary_zh = summary`。

## 5. 采集管线接线

`app/services/flow.py` 的 `collect` 分支，在现有抽取循环之后追加一段翻译循环，形态与抽取一致：

- 只处理本轮新增文章（沿用 `articles_repo.list_new_since(db, started)`）
- 单篇失败只把消息追加进 `errors`，不中断整轮；`partial` 状态语义不变
- 开关：`Settings.translate_enabled`（默认 `true`），关闭后整段跳过
- 预算：`Settings.llm_translate_max_tokens`（默认 1500）

## 6. 存量回填

新增 `backend/scripts/backfill_translations.py`：

- 取 `title_zh` 为空的文章，逐篇调用同一个 `translate_article`
- 打印进度与失败清单，支持 `--limit`
- 与采集流程共用 service，不重复实现提示词与解析

## 7. API 变更（增量）

`article_out`（`app/api/serializers.py`）增加两个字段，现有字段不动：

- `title_zh`、`summary_zh`（无译文时为 `null`）

`GET /api/regions/{code}/articles` 与 `GET /api/categories/{cat}/articles` 自动随之返回，接口签名与分页语义不变。

## 8. 前端结构与交互

### 8.1 滚动约束

`RegionPanel` 的新闻列表容器加固定最大高度 + 内部滚动，高度与地图卡片对齐：

- 常量放 `src/constants/mapBoard.ts`（`MAP_BOARD_STYLE.listMaxHeight`），不写死在组件里
- 头部（标题 + 返回按钮）留在容器外，不随列表滚动
- 列表为空/加载中时高度不塌陷，避免面板跳动

### 8.2 中文展示

- 新增纯函数 `src/utils/article.ts`：`displayTitle(item)` / `displaySummary(item)`，取中文，缺失回落原文；纯函数便于单测
- 列表条目结构：中文标题（链接，保持跳原文）→ 中文摘要（最多两行截断）→ 类别标签 · 来源 · 时间
- 摘要为空时整行不渲染，不留空白
- `src/api/types.ts` 的 `ArticleItem` 增加 `title_zh` / `summary_zh` 可空字段

## 9. 保留不变

- 抽取管线与 `article_regions` 打标逻辑
- 地图、图例、时间窗、类别筛选
- 四板块页、源管理、任务管理、待确认审核
- 已有 API 的字段与语义（只做新增）

## 10. 测试策略

后端（`pytest`）：

- `translator`：注入 fake provider 返回合法 JSON → 两列写入；返回非法 JSON / 抛错 → 不写库且不抛；已是中文 → 直接落原文；重复调用不覆盖已有译文
- `flow`：采集分支对新增文章调用翻译（fake provider），翻译失败时 run_logs 状态仍为 `partial` 而非 `failed`
- `serializers`：`article_out` 带出 `title_zh` / `summary_zh`
- `ensure_schema`：老库（无 `title_zh`）能被补上两列

前端（`vitest`）：

- `utils/article.ts`：有译文取译文、无译文回落原文、空摘要返回空

## 11. 风险与应对

| 风险 | 应对 |
| --- | --- |
| 采集时长增加（当前 92 篇抽取约 4 分钟，翻译再叠加一遍调用） | 先按逐篇实现并实测；若单轮超过可接受时长，再改为批量合并请求 |
| 模型返回非法 JSON 或截断 | 丢弃该篇，回填命令可重复执行补齐 |
| 存量 92 篇暂无中文 | 部署后跑一次回填脚本，前端在此之前回落原文，不影响可用性 |
| 翻译改变摘要长度导致列表观感变化 | 摘要限定 ≤120 字并两行截断，容器高度固定，不因内容变长 |

## 12. 迭代计划

1. 数据列 + `ensure_schema` 验证
2. 翻译 service + 单测
3. 采集管线接线 + 回填脚本
4. 前端中文展示 + 滚动约束 + 单测
5. 服务器部署并跑回填

## 13. 后续（不在本规范内）

- 中国与亚洲采集源的补充：需先在该服务器实测各候选 feed 可达性（BBC 已证明墙的存在），再单独出规范
