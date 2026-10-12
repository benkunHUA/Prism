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
  {
    key: "politics",
    label: "政治",
    color: "#5b21b6",
    path: "/politics",
    tagline: "谁在做决定 · 为什么 · 下一步",
    dailyTitle: "政治每日综述",
  },
  {
    key: "economy",
    label: "经济",
    color: "#065f46",
    path: "/economy",
    tagline: "数据说明现状 · 政策指明方向",
    dailyTitle: "宏观与政策简报",
  },
  {
    key: "finance",
    label: "金融",
    color: "#92400e",
    path: "/finance",
    tagline: "价格怎么变 · 为什么变 · 风险在哪",
    dailyTitle: "市场复盘",
  },
  {
    key: "military",
    label: "军事",
    color: "#991b1b",
    path: "/military",
    tagline: "谁有了什么新武器 · 仗打到哪一步",
    dailyTitle: "军事态势简报",
  },
];

export const CATEGORY_MAP = Object.fromEntries(
  CATEGORIES.map((item) => [item.key, item]),
) as Record<CategoryKey, CategoryMeta>;

export const CATEGORY_OPTIONS = CATEGORIES.map((item) => ({
  label: item.label,
  value: item.key,
}));
