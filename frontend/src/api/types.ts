export interface DashboardSummary {
  today_articles: number;
  today_analyses: number;
  source_health: { healthy: number; enabled: number };
  next_run_at: string | null;
  categories: string[];
}

export interface CategoryOverview {
  category: string;
  article_count: number;
  latest_daily_id: number | null;
  latest_daily_title: string | null;
}

export interface AnalysisSummary {
  id: number;
  kind: string;
  category: string;
  title: string;
  status: string;
  created_at: string;
  model: string | null;
}

export interface Citation {
  id: number;
  title: string;
  url: string;
  source_name: string | null;
}

export interface AnalysisDetail extends AnalysisSummary {
  content_md: string;
  period_start: string;
  period_end: string;
  error: string | null;
  citations: Citation[];
}

export interface ArticleItem {
  id: number;
  category: string;
  title: string;
  url: string;
  summary: string | null;
  source_name: string | null;
  published_at: string | null;
  fetched_at: string;
  lang: string | null;
}

export interface TimelineEvent {
  id: number;
  category: string;
  subtype: string;
  actor: string;
  region: string;
  occurred_at: string | null;
  summary: string;
  importance: string;
  verification_status: string;
  group_key: string | null;
  article_id: number | null;
  updated_at: string;
}

export interface WeaponItem {
  id: number;
  name: string;
  origin: string;
  weapon_type: string;
  params_text: string | null;
  lifecycle_status: string;
  verification_status: string;
  first_seen_at: string | null;
}

export interface IndicatorItem {
  id: number;
  indicator: string;
  region: string;
  period: string;
  value: number | null;
  unit: string | null;
  previous: number | null;
  forecast: number | null;
  released_at: string | null;
}

export interface StanceItem {
  id: number;
  topic: string;
  actor: string;
  stance_text: string;
  tone: string;
  stated_at: string | null;
  verification_status: string;
}

export interface SnapshotItem {
  id: number;
  asset_code: string;
  asset_name: string;
  asset_class: string;
  price: number | null;
  change_pct: number | null;
  captured_at: string;
  batch_id: string | null;
  source: string | null;
}

export type ModerationType = "timeline" | "weapon" | "stance" | "indicator";

export interface ModerationItem {
  type: ModerationType;
  id: number;
  category?: string;
  subtype?: string;
  summary?: string;
  importance?: string;
  name?: string;
  origin?: string;
  params_text?: string;
  lifecycle_status?: string;
  topic?: string;
  actor?: string;
  stance_text?: string;
  tone?: string;
  indicator?: string;
  region?: string;
  period?: string;
  value?: number | null;
  verification_status?: string;
}

export interface ModerationPatch {
  action: "confirm" | "reject" | "edit";
  summary?: string;
  importance?: string;
  params_text?: string;
  lifecycle_status?: string;
  stance_text?: string;
  tone?: string;
  value?: number;
}

export interface SourceItem {
  id: number;
  name: string;
  url: string;
  feed_type: string;
  lang: string;
  enabled: boolean;
  categories: string[];
  last_ok_at: string | null;
  last_error: string | null;
  error_count: number;
}

export interface SourceInput {
  name: string;
  url: string;
  feed_type: string;
  lang: string;
  enabled: boolean;
  categories: string[];
}

export interface TaskItem {
  id: number;
  name: string;
  kind: string;
  category: string | null;
  cron: string;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
}

export interface TaskInput {
  name: string;
  kind: string;
  category: string | null;
  cron: string;
  enabled: boolean;
}

export interface RunResult {
  task_id: number;
  status: string;
  fetched: number;
  new: number;
  errors: string[];
}

export interface RunLogItem {
  id: number;
  task_id: number | null;
  task_name: string | null;
  started_at: string;
  finished_at: string | null;
  status: string;
  fetched_count: number;
  new_count: number;
  error: string | null;
}
