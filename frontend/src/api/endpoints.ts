import { http } from "./client";
import type {
  AnalysisDetail,
  AnalysisSummary,
  ArticleItem,
  CategoryOverview,
  DashboardSummary,
  IndicatorItem,
  ModerationItem,
  ModerationPatch,
  RunLogItem,
  RunResult,
  SnapshotItem,
  SourceInput,
  SourceItem,
  StanceItem,
  TaskInput,
  TaskItem,
  TimelineEvent,
  WeaponItem,
} from "./types";

type QueryValue = string | number | undefined | null;

function queryString(params: Record<string, QueryValue>): string {
  const pairs = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`);
  return pairs.length ? `?${pairs.join("&")}` : "";
}

export const api = {
  dashboard: () => http.get<DashboardSummary>("/dashboard/summary"),
  categories: () => http.get<CategoryOverview[]>("/categories"),
  categoryAnalyses: (category: string, kind = "daily") =>
    http.get<{ items: AnalysisSummary[] }>(
      `/categories/${category}/analyses${queryString({ kind })}`,
    ),
  analysis: (id: number) => http.get<AnalysisDetail>(`/analyses/${id}`),
  articles: (category: string, limit = 20) =>
    http.get<{ items: ArticleItem[] }>(`/categories/${category}/articles${queryString({ limit })}`),

  timeline: (category: string, params: { subtype?: string; importance?: string } = {}) =>
    http.get<{ items: TimelineEvent[] }>(
      `/categories/${category}/timeline${queryString(params)}`,
    ),
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

  logs: (limit = 50) => http.get<{ items: RunLogItem[] }>(`/logs${queryString({ limit })}`),
};
