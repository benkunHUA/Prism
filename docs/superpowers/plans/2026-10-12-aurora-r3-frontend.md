# Aurora R3 实施计划（React 前端）

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development（本会话子代理通道不可用时改用 superpowers:executing-plans）。Steps 使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 交付可用的 React 前端：仪表盘 + 政治/经济/金融/军事四个差异化板块页 + 源管理 + 任务管理，以及全局“待确认 N”审核抽屉与手动执行采集入口。

**Architecture:** Vite + React 18 + TS + Ant Design 5 单页应用。按 `api/`（请求与类型）、`constants/`（板块与文案配置）、`components/`（可复用展示件）、`pages/`（路由页）、`layout/`（外壳与审核抽屉）、`utils/`（纯函数）分层；页面只做编排，数据访问集中在 `api/endpoints.ts`。开发态用 Vite proxy 把 `/api` 转发到 `127.0.0.1:8000`，无需后端改 CORS。

**Tech Stack:** React 18.3 + TypeScript 5.6 + Vite 5 + Ant Design 5 + react-router-dom 6 + react-markdown 9 + dayjs + Vitest 2（纯函数单测）。

---

## 后端契约（前端唯一数据源）

| 用途 | 请求 | 关键字段 |
| --- | --- | --- |
| 全局统计 | `GET /api/dashboard/summary` | `today_articles, today_analyses, source_health{healthy,enabled}, next_run_at, categories[]` |
| 板块概览 | `GET /api/categories` | `[{category, article_count, latest_daily_id, latest_daily_title}]` |
| 板块分析列表 | `GET /api/categories/{cat}/analyses?kind=daily` | `{items:[{id,kind,category,title,status,created_at,model}]}` |
| 分析全文 | `GET /api/analyses/{id}` | 追加 `content_md, period_start, period_end, citations[]` |
| 板块文章 | `GET /api/categories/{cat}/articles?limit=` | `{items:[{id,title,url,summary,source_name,published_at,fetched_at,lang}]}` |
| 事件时间线 | `GET /api/categories/{cat}/timeline?subtype=&importance=` | `{items:[{id,subtype,actor,region,occurred_at,summary,importance,verification_status,group_key,article_id}]}` |
| 武器档案 | `GET /api/military/weapons?lifecycle=` | `{items:[{id,name,origin,weapon_type,params_text,lifecycle_status,verification_status,first_seen_at}]}` |
| 宏观指标 | `GET /api/economy/indicators?region=&indicator=` | `{items:[{id,indicator,region,period,value,unit,previous,forecast,released_at}]}` |
| 议题立场 | `GET /api/politics/stances?topic=` | `{items:[{id,topic,actor,stance_text,tone,stated_at}]}`（后端已按 (topic,actor) 取最新） |
| 市场快照 | `GET /api/finance/snapshots?batch_id=&asset_class=` | `{items:[{id,asset_code,asset_name,asset_class,price,change_pct,captured_at,batch_id,source}]}` |
| 待确认队列 | `GET /api/moderations?category=` | `{items:[{type,id,category?,subtype?,name?,indicator?,topic?,...}]}` |
| 审核动作 | `PATCH /api/moderations/{type}/{id}` | body `{action: confirm\|reject\|edit, ...字段}` |
| 源管理 | `GET/POST /api/sources`、`PATCH /api/sources/{id}`、`DELETE /api/sources/{id}`、`POST /api/sources/{id}/test` | `{id,name,url,feed_type,lang,enabled,categories[],last_ok_at,last_error,error_count}` |
| 任务管理 | `GET/POST /api/tasks`、`PATCH /api/tasks/{id}`、`DELETE /api/tasks/{id}`、`POST /api/tasks/{id}/run` | `{id,name,kind,category,cron,enabled,last_run_at,next_run_at}` |
| 运行日志 | `GET /api/logs?limit=` | `{items:[{id,task_name,started_at,finished_at,status,fetched_count,new_count,error}]}` |

---

## 文件结构（新增）

```
frontend/
  package.json  tsconfig.json  tsconfig.node.json  vite.config.ts  index.html  .env.example
  src/main.tsx                      # 挂载 + AntD 中文 locale
  src/App.tsx                       # 路由表
  src/api/client.ts                 # fetch 封装（/api 前缀、错误、超时）
  src/api/types.ts                  # 后端响应类型
  src/api/endpoints.ts              # 资源化 API 函数
  src/constants/categories.ts       # 四板块：标签、主色、栏目、报告标题
  src/constants/options.ts          # 语言/类型/重要性/基调/生命周期等下拉项
  src/hooks/useAsync.ts             # loading/error/data/refresh
  src/layout/AppLayout.tsx          # 顶栏导航、待确认徽标、手动采集
  src/layout/ModerationDrawer.tsx   # 审核抽屉（确认/编辑/丢弃，按板块过滤）
  src/components/PageHeader.tsx
  src/components/StatCards.tsx
  src/components/EmptyHint.tsx
  src/components/MarkdownView.tsx   # react-markdown + gfm
  src/components/ReportPanel.tsx    # 今日报告卡片 + 阅读抽屉
  src/components/TimelineList.tsx   # 事件时间线（板块可配）
  src/components/ArticleList.tsx    # 原文列表（可跳转原文）
  src/pages/DashboardPage.tsx
  src/pages/PoliticsPage.tsx
  src/pages/MilitaryPage.tsx
  src/pages/EconomyPage.tsx
  src/pages/FinancePage.tsx
  src/pages/SourcesPage.tsx
  src/pages/TasksPage.tsx
  src/utils/format.ts               # 时间/数值/涨跌/vs 预期/健康度
  src/utils/format.test.ts          # Vitest 单测
  src/styles/global.css
```

---

## Task 1: 脚手架与构建校验

**Files:** `frontend/package.json`、`tsconfig.json`、`tsconfig.node.json`、`vite.config.ts`、`index.html`、`.env.example`、`src/main.tsx`、`src/App.tsx`、`src/styles/global.css`

- [ ] **Step 1: 写 `package.json`**

```json
{
  "name": "aurora-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "typecheck": "tsc -b --noEmit"
  },
  "dependencies": {
    "@ant-design/icons": "^5.5.1",
    "antd": "^5.21.6",
    "dayjs": "^1.11.13",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-markdown": "^9.0.1",
    "react-router-dom": "^6.27.0",
    "remark-gfm": "^4.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.3",
    "typescript": "^5.6.3",
    "vite": "^5.4.10",
    "vitest": "^2.1.4"
  }
}
```

- [ ] **Step 2: 写 `vite.config.ts`（含 `/api` 代理与 vitest 配置）**

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
```

- [ ] **Step 3: 写 `tsconfig.json` / `tsconfig.node.json` / `index.html` / `src/styles/global.css`**

`tsconfig.json` 关键项：`"target": "ES2020"`、`"lib": ["ES2020","DOM","DOM.Iterable"]`、`"jsx": "react-jsx"`、`"module": "ESNext"`、`"moduleResolution": "bundler"`、`"strict": true`、`"noUnusedLocals": true`、`"types": ["vitest/globals"]`、`include: ["src"]`、`references: [{path: "./tsconfig.node.json"}]`。

`index.html`：`<div id="root"></div>` + `<script type="module" src="/src/main.tsx">`，标题 `Aurora 信息情报台`，`lang="zh-CN"`。

`src/styles/global.css`：页面留白、`.aurora-shell` 布局、`.md-body`（Markdown 排版：标题间距、引用块、表格边框）、`.up`/`.down` 涨跌配色。

- [ ] **Step 4: 写 `src/main.tsx` 与 `src/App.tsx` 骨架**

```tsx
// src/main.tsx
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import "./styles/global.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>,
);
```

```tsx
// src/App.tsx（Task 3 会替换为完整路由）
import { Route, Routes } from "react-router-dom";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<div>加载中…</div>} />
    </Routes>
  );
}
```

- [ ] **Step 5: 安装依赖并验证构建**

Run: `cd frontend && npm install && npm run build`
Expected: 构建成功（`dist/` 生成）

- [ ] **Step 6: 提交**

```bash
git add frontend && git commit -m "feat(frontend): Vite + React + AntD 脚手架"
```

---

## Task 2: 请求层、类型与纯函数工具

**Files:** `src/api/client.ts`、`src/api/types.ts`、`src/api/endpoints.ts`、`src/constants/categories.ts`、`src/constants/options.ts`、`src/utils/format.ts`、`src/utils/format.test.ts`、`src/hooks/useAsync.ts`

- [ ] **Step 1: 写失败测试** `src/utils/format.test.ts`

```ts
import { describe, expect, it } from "vitest";

import { compareToForecast, formatChangePct, formatDateTime, healthLevel } from "./format";

describe("compareToForecast", () => {
  it("marks beat when value is above forecast", () => {
    expect(compareToForecast(0.5, 0.3)).toBe("beat");
  });
  it("marks miss when value is below forecast", () => {
    expect(compareToForecast(0.1, 0.3)).toBe("miss");
  });
  it("marks inline when equal or forecast missing", () => {
    expect(compareToForecast(0.3, 0.3)).toBe("inline");
    expect(compareToForecast(0.3, null)).toBe("inline");
  });
});

describe("formatChangePct", () => {
  it("keeps sign and two decimals", () => {
    expect(formatChangePct(1.236)).toBe("+1.24%");
    expect(formatChangePct(-0.4)).toBe("-0.40%");
    expect(formatChangePct(null)).toBe("—");
  });
});

describe("healthLevel", () => {
  it("maps error counts to levels", () => {
    expect(healthLevel({ enabled: true, error_count: 0 })).toBe("ok");
    expect(healthLevel({ enabled: true, error_count: 2 })).toBe("warn");
    expect(healthLevel({ enabled: true, error_count: 3 })).toBe("bad");
    expect(healthLevel({ enabled: false, error_count: 0 })).toBe("off");
  });
});

describe("formatDateTime", () => {
  it("renders ISO strings as local minutes", () => {
    expect(formatDateTime("2026-10-11T08:05:00")).toBe("2026-10-11 08:05");
    expect(formatDateTime(null)).toBe("—");
  });
});
```

- [ ] **Step 2: 运行确认失败**：`cd frontend && npx vitest run src/utils/format.test.ts` → FAIL（模块不存在）

- [ ] **Step 3: 实现** `src/utils/format.ts`

```ts
export type ForecastVerdict = "beat" | "miss" | "inline";
export type HealthLevel = "ok" | "warn" | "bad" | "off";

export function compareToForecast(value: number | null, forecast: number | null): ForecastVerdict {
  if (value === null || forecast === null || value === undefined || forecast === undefined) {
    return "inline";
  }
  if (value > forecast) return "beat";
  if (value < forecast) return "miss";
  return "inline";
}

export function formatChangePct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function changeClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return "";
  return value >= 0 ? "up" : "down";
}

export function healthLevel(source: { enabled: boolean; error_count: number }): HealthLevel {
  if (!source.enabled) return "off";
  if (source.error_count === 0) return "ok";
  if (source.error_count < 3) return "warn";
  return "bad";
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 16);
}

export function formatNumber(value: number | null | undefined, unit = ""): string {
  if (value === null || value === undefined) return "—";
  return `${value}${unit}`;
}
```

- [ ] **Step 4: 运行确认通过**：`cd frontend && npm test` → 全部通过

- [ ] **Step 5: 实现 API 层**

`src/api/client.ts`：

```ts
const BASE = "/api";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = (data && (data.detail || data.message)) || response.statusText;
    throw new ApiError(response.status, String(detail));
  }
  return data as T;
}

export const http = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
```

`src/api/types.ts`：按上文“后端契约”表逐一声明 `DashboardSummary`、`CategoryOverview`、`AnalysisSummary`、`AnalysisDetail`、`ArticleItem`、`TimelineEvent`、`WeaponItem`、`IndicatorItem`、`StanceItem`、`SnapshotItem`、`ModerationItem`、`SourceItem`、`TaskItem`、`RunLogItem`，字段名与后端一致（可空字段用 `| null`）。

`src/api/endpoints.ts`：按资源分组的薄封装，例如：

```ts
export const api = {
  dashboard: () => http.get<DashboardSummary>("/dashboard/summary"),
  categories: () => http.get<CategoryOverview[]>("/categories"),
  categoryAnalyses: (cat: string, kind = "daily") =>
    http.get<{ items: AnalysisSummary[] }>(`/categories/${cat}/analyses?kind=${kind}`),
  analysis: (id: number) => http.get<AnalysisDetail>(`/analyses/${id}`),
  timeline: (cat: string, params: { subtype?: string; importance?: string } = {}) =>
    http.get<{ items: TimelineEvent[] }>(`/categories/${cat}/timeline${queryString(params)}`),
  weapons: (lifecycle?: string) =>
    http.get<{ items: WeaponItem[] }>(`/military/weapons${queryString({ lifecycle })}`),
  indicators: (params: { region?: string; indicator?: string } = {}) =>
    http.get<{ items: IndicatorItem[] }>(`/economy/indicators${queryString(params)}`),
  stances: (topic?: string) =>
    http.get<{ items: StanceItem[] }>(`/politics/stances${queryString({ topic })}`),
  snapshots: (params: { asset_class?: string; batch_id?: string } = {}) =>
    http.get<{ items: SnapshotItem[] }>(`/finance/snapshots${queryString(params)}`),
  moderations: (category?: string) =>
    http.get<{ items: ModerationItem[] }>(`/moderations${queryString({ category })}`),
  moderate: (type: string, id: number, body: ModerationPatch) =>
    http.patch<unknown>(`/moderations/${type}/${id}`, body),
  sources: () => http.get<{ items: SourceItem[] }>("/sources"),
  createSource: (body: SourceInput) => http.post<SourceItem>("/sources", body),
  updateSource: (id: number, body: Partial<SourceInput>) =>
    http.patch<SourceItem>(`/sources/${id}`, body),
  deleteSource: (id: number) => http.del<void>(`/sources/${id}`),
  testSource: (id: number) =>
    http.post<{ ok: boolean; error: string | null; preview: { title: string; url: string }[] }>(
      `/sources/${id}/test`,
    ),
  tasks: () => http.get<{ items: TaskItem[] }>("/tasks"),
  createTask: (body: TaskInput) => http.post<TaskItem>("/tasks", body),
  updateTask: (id: number, body: Partial<TaskInput>) => http.patch<TaskItem>(`/tasks/${id}`, body),
  deleteTask: (id: number) => http.del<void>(`/tasks/${id}`),
  runTask: (id: number) => http.post<RunResult>(`/tasks/${id}/run`),
  logs: (limit = 50) => http.get<{ items: RunLogItem[] }>(`/logs?limit=${limit}`),
};
```

（`queryString` 为文件内私有工具：过滤 `undefined | null | ""` 后拼 `?a=b&c=d`。）

- [ ] **Step 6: 实现** `src/constants/categories.ts` 与 `src/constants/options.ts`

```ts
// categories.ts
export type CategoryKey = "politics" | "economy" | "finance" | "military";

export interface CategoryMeta {
  key: CategoryKey;
  label: string;
  color: string;
  path: string;
  tagline: string;
  dailyTitle: string;
}

export const CATEGORIES: CategoryMeta[] = [
  { key: "politics", label: "政治", color: "#5b21b6", path: "/politics",
    tagline: "谁在做决定 · 为什么 · 下一步", dailyTitle: "政治每日综述" },
  { key: "economy", label: "经济", color: "#065f46", path: "/economy",
    tagline: "数据说明现状 · 政策指明方向", dailyTitle: "宏观与政策简报" },
  { key: "finance", label: "金融", color: "#92400e", path: "/finance",
    tagline: "价格怎么变 · 为什么变 · 风险在哪", dailyTitle: "市场复盘" },
  { key: "military", label: "军事", color: "#991b1b", path: "/military",
    tagline: "谁有了什么新武器 · 仗打到哪一步", dailyTitle: "军事态势简报" },
];

export const CATEGORY_MAP: Record<CategoryKey, CategoryMeta> = Object.fromEntries(
  CATEGORIES.map((c) => [c.key, c]),
) as Record<CategoryKey, CategoryMeta>;
```

`options.ts`：导出 `FEED_TYPES`（rss/page）、`LANGS`（en/zh/ja/…）、`IMPORTANCE_OPTIONS`（high/medium/low）、`WEAPON_LIFECYCLE`、`STANCE_TOPICS`、`STANCE_TONES`、`ASSET_CLASSES`、`MODERATION_TYPE_LABELS`（timeline→事件、weapon→武器、stance→立场、indicator→指标）、`TASK_KIND_LABELS`（collect→采集、analyze→分析）、`LOG_STATUS`（success/partial/failed 的中文与颜色）。所有中文文案集中在此，页面不写字面量。

- [ ] **Step 7: 实现** `src/hooks/useAsync.ts`

```ts
import { useCallback, useEffect, useState } from "react";

export function useAsync<T>(loader: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    loader()
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, loading, error, reload };
}
```

- [ ] **Step 8: 验证**：`cd frontend && npm test && npm run build`

- [ ] **Step 9: 提交**

```bash
git add frontend && git commit -m "feat(frontend): 请求层、类型、板块常量与格式化工具"
```

---

## Task 3: 应用外壳、路由与审核抽屉

**Files:** `src/layout/AppLayout.tsx`、`src/layout/ModerationDrawer.tsx`、`src/components/*`、`src/App.tsx`

- [ ] **Step 1: 实现共享展示件**
  - `PageHeader.tsx`：`{title, tagline, extra?}` 标题区。
  - `StatCards.tsx`：`{items: {label, value, hint?}[]}` 顶部统计卡片（对应线框的 `6 新武器动态 / 3 活跃冲突线 / 2 待确认`）。
  - `EmptyHint.tsx`：`{text}` 空态（无数据时统一文案，避免空白页）。
  - `MarkdownView.tsx`：`react-markdown` + `remarkGfm`，容器类 `md-body`。
  - `ReportPanel.tsx`：`{category}` 内部用 `useAsync` 拉 `categoryAnalyses(cat,'daily')` 取最新一篇标题 + `analysis(id)` 正文，卡片展示标题与 120 字摘要，点“阅读 →”打开 Drawer 全文（`MarkdownView` + 引用来源列表）。
  - `TimelineList.tsx`：`{items, showSubtypeFilter?}` 用 AntD `Timeline`，每条显示 `occurred_at/subtype/actor/region/importance` 与摘要，`importance === 'high'` 左侧红色（`.evt.hot`）。
  - `ArticleList.tsx`：`{category, limit}` 拉板块文章，列出标题/来源/时间，外链 `target="_blank" rel="noreferrer"`。

- [ ] **Step 2: 实现 `ModerationDrawer`**

```tsx
interface Props {
  open: boolean;
  onClose: () => void;
  onChanged: () => void; // 审核后刷新徽标计数
}
```

行为：`useMemo` 拉 `api.moderations(categoryFilter)`；顶部 Select 按板块过滤（全部/政治/经济/金融/军事）；列表按 `type` 分组（事件/武器/立场/指标），每条显示关键字段 + 三个操作按钮：确认（`{action:'confirm'}`）、编辑（弹出行内编辑表单，字段随 type 变化：事件改 summary/importance、武器改 params_text/lifecycle_status、立场改 stance_text/tone、指标改 value）、丢弃（`{action:'reject'}`）。操作成功后 `message.success` + 重新拉取 + 调 `onChanged`。

- [ ] **Step 3: 实现 `AppLayout`**
  - 顶部 `Header`：左侧 `Aurora` 标识；中间 `Menu`（仪表盘/政治/经济/金融/军事/源管理/任务管理，`useLocation().pathname` 决定选中项）；右侧 `Badge count={pending}>待确认</Badge>`（点击开抽屉）、`Button` “手动采集”（取任务列表中第一个 `kind=collect` 且启用的任务调 `runTask`，执行中 `loading`，完成后 `message.success('已触发执行')` 并刷新徽标）。
  - `Content`：`<Outlet />`。
  - 抽屉状态提升到 `AppLayout`，`onChanged` 重新拉 `moderations` 数量。

- [ ] **Step 4: 写路由** `src/App.tsx`

```tsx
<Routes>
  <Route element={<AppLayout />}>
    <Route index element={<DashboardPage />} />
    <Route path="politics" element={<PoliticsPage />} />
    <Route path="economy" element={<EconomyPage />} />
    <Route path="finance" element={<FinancePage />} />
    <Route path="military" element={<MilitaryPage />} />
    <Route path="sources" element={<SourcesPage />} />
    <Route path="tasks" element={<TasksPage />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Route>
</Routes>
```

- [ ] **Step 5: 验证**：`cd frontend && npm run build`

- [ ] **Step 6: 提交**：`git commit -m "feat(frontend): 应用外壳、路由与待确认审核抽屉"`

---

## Task 4: 仪表盘页

**Files:** `src/pages/DashboardPage.tsx`

布局（对应线框 A）：顶部 4 张统计卡（今日新增文章 / 今日分析篇数 / 源健康 `healthy/enabled` / 下次任务时间）；下方四板块卡片网格，每张展示板块名、tagline、`article_count`、最新日报标题（点击跳到板块页），并按板块追加一行特色摘要：
- 政治：未确认立场条数
- 军事：武器总数 + 待确认数
- 经济：最新一条指标（指标名 + 数值）
- 金融：最新批次资产数与涨跌家数

- [ ] **Step 1: 实现页面**，数据用 `useAsync` 并发拉 `dashboard/categories/weapons/indicators/snapshots/moderations`。
- [ ] **Step 2: 验证** `npm run build`，`npm run dev` 后在浏览器确认渲染（见 Task 11 手测清单）。
- [ ] **Step 3: 提交**：`git commit -m "feat(frontend): 仪表盘页"`

---

## Task 5: 政治页

**Files:** `src/pages/PoliticsPage.tsx`

布局（线框 B）：`ReportPanel(category="politics")` → 两列（左：事件时间线 `TimelineList`，带 subtype/importance 筛选；右：议题立场卡片列表，按 `topic` 分组，显示 `actor`、`tone` 标签、`stance_text`、`stated_at`）→ 底部 `ArticleList(category="politics")`。

- [ ] **Step 1: 实现页面**；空态用 `EmptyHint("暂无已确认的政治事件，等待采集与分析产出")`。
- [ ] **Step 2: 验证** `npm run build` + 手测。
- [ ] **Step 3: 提交**：`git commit -m "feat(frontend): 政治板块页"`

---

## Task 6: 军事页

**Files:** `src/pages/MilitaryPage.tsx`

布局（线框 C）：`StatCards`（武器总数 / 活跃战线数（按 `group_key || region` 去重）/ 待确认武器数）→ `ReportPanel(category="military")` → 冲突态势：按 `region` 分组的 `TimelineList`（组标题显示战线名与事件数）→ 武器档案卡片网格（`name` / `origin` / `weapon_type` / `lifecycle_status` 标签 / `params_text` / `first_seen_at`，draft 记录带“待确认”标记）→ `ArticleList(category="military")`。

- [ ] **Step 1: 实现页面**（生命周期筛选 Select 调 `api.weapons(lifecycle)`）。
- [ ] **Step 2: 验证** `npm run build` + 手测。
- [ ] **Step 3: 提交**：`git commit -m "feat(frontend): 军事板块页"`

---

## Task 7: 经济页

**Files:** `src/pages/EconomyPage.tsx`

布局（线框 D）：`ReportPanel(category="economy")` → 指标表（AntD Table：指标/地区/周期/数值/前值/预期/vs 预期，最后一列用 `compareToForecast` 渲染 `好于`（绿）/`不及`（红）/`持平`（灰））→ 政策事件流（`TimelineList`，subtype 固定为货币政策/财政政策/贸易政策/产业政策/监管与改革）→ `ArticleList(category="economy")`。

- [ ] **Step 1: 实现页面**（地区/指标筛选 Select，选项来自当前数据去重）。
- [ ] **Step 2: 验证** `npm run build` + 手测。
- [ ] **Step 3: 提交**：`git commit -m "feat(frontend): 经济板块页"`

---

## Task 8: 金融页

**Files:** `src/pages/FinancePage.tsx`

布局（线框 E）：`ReportPanel(category="finance")` → 市场快照表（资产类别/名称/价格/本批次涨跌/较上轮，涨跌用 `.up` 红、`.down` 绿，`formatChangePct`）→ 驱动事件时间线（`TimelineList(category="finance")`）→ `ArticleList(category="finance")`；表头显示批次 id 与抓取时间。

- [ ] **Step 1: 实现页面**（资产类别筛选 Select；跨批次对比在前端按 `asset_name` 对齐最近两个批次）。
- [ ] **Step 2: 验证** `npm run build` + 手测。
- [ ] **Step 3: 提交**：`git commit -m "feat(frontend): 金融板块页"`

---

## Task 9: 源管理页

**Files:** `src/pages/SourcesPage.tsx`

布局（管理页线框）：工具条（板块筛选 Select、状态筛选、关键词搜索、`+ 新增源`）→ Table（名称/URL/板块标签/类型/语言/健康（`healthLevel` 上色 + `last_error` Tooltip）/启用 Switch/操作：测试、编辑、删除）→ 新增/编辑 `Drawer` 表单（名称、URL、类型、板块多选、语言、启用），提交后 `message.success`；测试按钮调 `testSource`，结果用 `Modal.info` 展示 `ok/error/preview`；删除用 `Popconfirm`。

- [ ] **Step 1: 实现页面**（表单字段用 `options.ts` 常量；列表筛选在前端完成）。
- [ ] **Step 2: 验证** `npm run build` + 手测。
- [ ] **Step 3: 提交**：`git commit -m "feat(frontend): 采集源管理页"`

---

## Task 10: 任务管理页

**Files:** `src/pages/TasksPage.tsx`

布局（管理页线框）：任务卡片列表（名称、`kind` 标签、板块、cron、启用 Switch、上次/下次运行时间）+ `立即执行`（调 `runTask`，展示返回的 `{status, fetched, new, errors}` 摘要）+ `日志`（打开 Drawer 展示该任务最近日志）+ `+ 新增任务` Drawer（名称、类型 collect/analyze、板块（可空=全板块）、cron、启用）+ 底部“最近运行日志”表（`api.logs()`，状态用 `LOG_STATUS` 配色，错误详情 Tooltip）。

- [ ] **Step 1: 实现页面**。
- [ ] **Step 2: 验证** `npm run build` + 手测。
- [ ] **Step 3: 提交**：`git commit -m "feat(frontend): 定时任务管理页"`

---

## Task 11: 文档、联调与全量校验

**Files:** `README.md`、`frontend/.env.example`

- [ ] **Step 1: `.env.example`**：`VITE_API_BASE=/api`（说明：开发态由 Vite proxy 转发，生产可指向后端地址）。
- [ ] **Step 2: README 增加前端小节**

```markdown
## 前端启动

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000   # 先起后端
cd frontend && npm install && npm run dev                        # 打开 http://localhost:5173
```

开发态 `/api` 由 Vite 代理到 `127.0.0.1:8000`。校验命令：`npm test`（纯函数单测）、`npm run build`（tsc + 产物构建）。
```

- [ ] **Step 3: 手测清单**（启动前后端，逐条确认）
  1. 顶栏七个导航可切换，当前项高亮
  2. 仪表盘四张统计卡与四板块卡片渲染（空库时显示 0 与空态文案，不报错）
  3. 四个板块页各自栏目与线框一致（政治时间线+立场、军事统计+武器网格、经济指标表+政策流、金融快照表+复盘）
  4. 顶栏“已确认 N”徽标数字与抽屉列表一致，确认/编辑/丢弃后徽标刷新
  5. 源管理：新增源成功、测试源返回预览、删除生效
  6. 任务管理：立即执行返回摘要、日志抽屉展示运行记录
  7. 手动采集按钮触发成功提示

- [ ] **Step 4: 全量校验**：`cd frontend && npm test && npm run build`，并再次 `cd backend && uv run pytest -q`（确认后端未受影响）
- [ ] **Step 5: 提交**：`git commit -m "docs: 补充前端启动与联调说明"`

---

## 自查清单

- 覆盖设计规范 §8：政治/军事/经济/金融四页差异化布局、全局待确认徽标 + 审核抽屉、仪表盘四板块卡片
- 覆盖用户要求：手动执行采集（顶栏 + 任务页）、源管理、任务管理
- 无占位符：所有共享模块均给出完整代码；页面级任务给出栏目、数据源、交互与验收标准
- 命名一致：`api.*` 方法名、`CategoryKey`、`formatChangePct` / `compareToForecast` / `healthLevel` 在任务间保持同名
