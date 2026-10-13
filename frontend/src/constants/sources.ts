import type { RegionOption, SourceInput } from "../api/types";

export const EMPTY_SOURCE_FORM: SourceInput = {
  name: "",
  url: "",
  feed_type: "rss",
  lang: "en",
  region: "",
  enabled: true,
  categories: [],
};

export const SOURCE_TEXT = {
  createTitle: "新增采集源",
  editTitle: (name: string) => `编辑：${name}`,
  emptyCell: "—",
  nameLabel: "名称",
  namePlaceholder: "例如 Reuters Business",
  urlLabel: "URL",
  urlPlaceholder: "https://example.com/feed",
  feedTypeLabel: "类型",
  categoriesLabel: "板块",
  categoriesRequired: "至少选择一个板块",
  regionLabel: "来源地区（打标失败时的兜底）",
  regionTooltip: "只在该源的文章没能从正文识别出发生地时使用",
  regionPlaceholder: "留空则不参与兜底",
  langLabel: "语言",
  enabledLabel: "启用",
} as const;

/** 地区下拉选项：名称 + code，清单只来自后端 /api/regions。 */
export function regionSelectOptions(regions: RegionOption[]): { label: string; value: string }[] {
  return regions.map((item) => ({ label: `${item.name}（${item.code}）`, value: item.code }));
}

/** 表格展示来源地区：优先词表名称，词表外的历史 code 原样显示。 */
export function regionDisplayName(code: string, names: Map<string, string>): string {
  if (!code) return SOURCE_TEXT.emptyCell;
  return names.get(code) ?? code;
}
