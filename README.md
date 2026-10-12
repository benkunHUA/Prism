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

## 板块结构化与审核 API

- `GET /api/categories/{cat}/timeline` 事件时间线
- `GET /api/military/weapons`、`GET /api/economy/indicators`
- `GET /api/politics/stances`、`GET /api/finance/snapshots`
- `GET /api/moderations`、`PATCH /api/moderations/{type}/{id}`（confirm/edit/reject）

## 行情快照（默认关闭）

在 `backend/.env` 中启用（默认行情源为东方财富批量接口）：

```dotenv
MARKET_PROVIDER=eastmoney
MARKET_SYMBOLS=index|标普500=100.SPX,index|道琼斯=100.DJIA,index|纳斯达克=100.NDX,index|美元指数=100.UDI,commodity|伦敦金=101.GC00Y,commodity|纽约原油=101.CL00Y
```

实测 Stooq 免费接口已失效、Yahoo 在当前网络不可用；`MARKET_PROVIDER=stooq` 仍保留为备选。行情抓取失败只记日志，不影响采集/分析。

## 主要 API

- `GET /api/dashboard/summary` 仪表盘统计
- `GET /api/categories`、`GET /api/categories/{cat}/articles`、`GET /api/categories/{cat}/analyses`
- `GET /api/analyses/{id}`、`GET /api/articles/{id}`
- `GET|POST /api/sources`、`PATCH|DELETE /api/sources/{id}`、`POST /api/sources/{id}/test`
- `GET|POST /api/tasks`、`PATCH|DELETE /api/tasks/{id}`、`POST /api/tasks/{id}/run`
- `GET /api/logs`
