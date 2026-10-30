# Aurora

全球信息收集与分析系统。仓库结构：

- `backend/`：FastAPI + SQLite + APScheduler（计划 A）
- `frontend/`：React + Vite + TS + Ant Design（计划 B）

## 后端启动

```bash
cd backend
cp .env.example .env   # 填入 DEEPSEEK_API_KEY
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

测试：`cd backend && uv run pytest -q`

## 前端启动

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000   # 先起后端
cd frontend && npm install && npm run dev                        # 打开 http://localhost:5173
```

开发态 `/api` 由 Vite 代理到 `127.0.0.1:8000`（可用 `frontend/.env` 的 `VITE_API_BASE` 覆盖）。
校验命令：`npm test`（纯函数单测）、`npm run build`（类型检查 + 产物构建）。

页面：看板（世界地图）、政治/经济/金融/军事四个差异化板块页、源管理、任务管理；顶栏含“待确认”审核抽屉与“手动采集”按钮。

看板即世界地图：底层按国家填色表示新闻热度，上层彩色点表示各板块分布，点击地区在右栏就地查看该地区新闻，
时间窗默认近 24 小时（可切 7 / 30 天）。图上「未定位 N 条」表示该时间窗内没有地理标签的文章数。

- 地区词表在 `backend/app/core/geo.py`（国家 code + 中文名 + 别名 + 坐标，另含台海/加沙/南海/红海/北极等热点区）。
  增补国家只需在词表里加一条，再重跑一次底图脚本：
  `cd frontend && node scripts/build-world-geo.mjs /tmp/ne_110m_countries.geojson`，
  `backend/tests/test_geo_asset.py` 会检查词表里的每个国家在底图里都有几何。
- 文章地区标签由抽取管线顺带产出（不额外调用 LLM），抽取关闭或识别失败时回退到「来源地区」；
  来源地区在源管理页配置。

## 四板块每日报告模板

每类板块的每日分析（`kind=daily`）与快讯（`kind=brief`）使用各自的标题与固定章节，
由 `backend/app/services/reports/specs.py` 集中定义（改文案不动逻辑）：

| 板块 | 每日报告 | 固定章节 |
| --- | --- | --- |
| 政治 | 政治每日综述 | 今日要闻 / 事件脉络 / 议题立场变化 / 下一步看点 |
| 军事 | 军事态势简报 | 态势要点 / 新武器与装备动态 / 冲突进展 / 演习·军贸·防务快讯 / 态势展望 |
| 经济 | 宏观与政策简报 | 数据要点 / 政策动作与影响对象 / 机构预测调整 / 传导提示 |
| 金融 | 市场复盘 | 资产表现 / 国际原油 / 驱动事件归因 / 资金与风险信号 / 明日关注 |

生成提示词会把该板块已确认的结构化条目（武器档案、事件时间线、议题立场、宏观指标、
市场快照）作为附加素材注入，并要求与新闻材料冲突时以材料为准。

金融板块额外做了原油增强：内置 EIA 今日能源、OilPrice 原油与能源信源；
分析选材时为原油相关文章保留约三分之一名额；金融页单列 WTI、布伦特价格、WTI-Brent 价差，
报告固定章节「国际原油」会结合 OPEC+ 供给、库存、地缘风险、美元与需求变化分析。

### 模型与输出预算

默认 `LLM_MODEL=deepseek-chat`（非推理模型）。如果换成推理模型（例如 `deepseek-v4-flash`），
reasoning 也计入 `max_tokens`，会因预算耗尽只拿到推理过程、正文为空。两种应对方式：

```dotenv
# 方式一（推荐）：关闭思考模式，采集/简报类任务不需要思维链
LLM_THINKING=disabled

# 方式二：保留推理，但把输出预算调大
LLM_BRIEF_MAX_TOKENS=3000
LLM_DAILY_MAX_TOKENS=12000
LLM_EXTRACT_MAX_TOKENS=4000
```

后端已做保护：LLM 返回空内容或被截断（`finish_reason=length`）时直接报错并丢弃，
不会把空报告写入分析列表；错误会出现在任务日志里。

## 板块结构化与审核 API

- `GET /api/categories/{cat}/timeline?days=30` 事件时间线（默认近 30 天）
- `GET /api/categories/{cat}/articles?days=30` 原文材料（默认按发布时间的近 30 天）
- `GET /api/military/weapons`、`GET /api/economy/indicators`
- `GET /api/politics/stances`、`GET /api/finance/snapshots`
- `GET /api/moderations`、`PATCH /api/moderations/{type}/{id}`（confirm/edit/reject）

## 行情快照

在 `backend/.env` 中填入标的即启用（默认行情源为东方财富批量接口，一次请求取回全部标的）：

```dotenv
MARKET_PROVIDER=eastmoney
MARKET_SYMBOLS=index|美元指数=100.UDI,index|标普500=100.SPX,index|恒生指数=100.HSI,index|上证指数=1.000001,rate|美债10年期收益率=171.US10Y,fx|离岸人民币=133.USDCNH,commodity|COMEX黄金=101.GC00Y,commodity|NYMEX原油=102.CL00Y,equity|苹果=105.AAPL,equity|腾讯控股=116.00700
```

格式为 `类别|名称=东方财富secid`，逗号分隔；`MARKET_SYMBOLS` 留空即关闭行情快照。
类别取值与前端筛选下拉一致：`index` / `rate` / `fx` / `commodity` / `volatility` / `crypto` / `equity`。
仓库里的 `.env.example` 已填好一组逐个实测可用的标的，可直接复制。

### 怎么拿到真实可用的 secid

secid 就是 `市场号.代码`，例如 `100.SPX`、`1.000001`、`116.00700`。不用背市场号，仓库自带查询脚本，
一次完成「按关键词搜候选 → 回验能不能取到报价 → 输出可粘贴片段」：

```bash
cd backend
uv run python scripts/find_secid.py 原油 --class commodity
uv run python scripts/find_secid.py 黄金 白银 --class commodity --count 5
```

输出形如：

```
== 原油 ==
  secid         名称                    类型      报价
  112.B00Y      布伦特原油当月连续      期货      107.16 +2.33%
  102.CL00Y     NYMEX原油               期货      93.92 +2.25%
  0.000956      中原油气                深A       0.0 +0.00%

  可粘贴片段（类别=commodity，多个之间用英文逗号连接）：
    commodity|布伦特原油当月连续=112.B00Y
    commodity|NYMEX原油=102.CL00Y
```

「报价」列拿到价格才说明这个 secid 能用；脚本会把没有报价的候选从片段里剔除。
关键词搜到的第一个结果不一定是你想要的标的（搜"黄金"第一个是黄金板块 `90.BK1617`，
指数/期货要往后找），所以务必看「报价」列确认。

常用市场号：`1` 沪市、`0` 深市、`100` 国际指数、`101` COMEX 金属、`102` NYMEX 能源、`112` IPE 布伦特原油、`105` 纳斯达克、`106` 纽交所、`107` 美交所、`116` 港股、`119`/`133` 外汇、`171` 美债收益率。

已知坑：

- `push2` 在非交易时段或限流时会把请求 302 到 `push2delay.eastmoney.com`，代码已开启跟随重定向，否则会拿到空响应体；
- 直接用 `curl` 调这两个接口容易被风控返回空响应（`http=000`），中文关键词还会因为没 URL 编码报 400，建议用上面的脚本；
- 常见误写：纽约原油是 `102.CL00Y`，不是 `101.CL00Y`。

实测 Stooq 免费接口已失效、Yahoo 在当前网络不可用；`MARKET_PROVIDER=stooq` 仍保留为备选。行情抓取失败只记日志，不影响采集/分析。

## 中文译文

文章标题与摘要在采集落库阶段批量翻译（`translate_enabled` 开关、`translate_batch_size` 批大小，
一批一次模型调用），写入 `articles.title_zh` / `articles.summary_zh`；缺译文时前端回落显示原文。
译文只做翻译与压缩，不补充原文没有的信息；原文已是中文的条目直接落原文，不调模型。

存量文章用下面这条命令补齐，可反复执行（只处理 `title_zh IS NULL` 的条目）：

```bash
cd backend && uv run python scripts/backfill_translations.py
```

老库启动时由 `ensure_schema` 自动补上这两列，不需要手工迁移。

## 主要 API

- `GET /api/dashboard/summary` 仪表盘统计
- `GET /api/dashboard/geo?window=24h|7d|30d` 看板地区聚合
- `GET /api/regions` 地区选项（国家 + 热点区）
- `GET /api/regions/{code}/articles?window=&category=` 某地区文章列表
- `GET /api/categories`、`GET /api/categories/{cat}/articles`、`GET /api/categories/{cat}/analyses`
- `GET /api/analyses/{id}`、`GET /api/articles/{id}`
- `GET|POST /api/sources`、`PATCH|DELETE /api/sources/{id}`、`POST /api/sources/{id}/test`
- `GET|POST /api/tasks`、`PATCH|DELETE /api/tasks/{id}`、`POST /api/tasks/{id}/run`
- `GET /api/logs`

## 部署（单端口）

后端可以直接把前端构建产物挂到同一个端口，免 CORS、免反向代理：

```bash
cd frontend && npm run build                     # 产物在 frontend/dist
cd ../backend
export STATIC_DIR=../frontend/dist
export AUTH_USER=aurora AUTH_PASSWORD=<访问口令>
uv run uvicorn app.main:app --host 0.0.0.0 --port 3000 --workers 1
```

- `STATIC_DIR` 留空则只提供 API（本地开发走 Vite 代理）；`/assets/*` 走静态文件，
  其余未命中路径回落 `index.html`，`/api/*` 未命中仍返回 404。
- `AUTH_PASSWORD` 非空即对整站启用 HTTP Basic 鉴权；留空表示公开访问。
- **`--workers 1` 是硬要求**：APScheduler 是进程内调度，多 worker 会让采集重复触发。
