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
