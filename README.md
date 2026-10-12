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

页面：仪表盘、政治/经济/金融/军事四个差异化板块页、源管理、任务管理；顶栏含“待确认”审核抽屉与“手动采集”按钮。

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

- `GET /api/categories/{cat}/timeline` 事件时间线
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

## 主要 API

- `GET /api/dashboard/summary` 仪表盘统计
- `GET /api/categories`、`GET /api/categories/{cat}/articles`、`GET /api/categories/{cat}/analyses`
- `GET /api/analyses/{id}`、`GET /api/articles/{id}`
- `GET|POST /api/sources`、`PATCH|DELETE /api/sources/{id}`、`POST /api/sources/{id}/test`
- `GET|POST /api/tasks`、`PATCH|DELETE /api/tasks/{id}`、`POST /api/tasks/{id}/run`
- `GET /api/logs`
