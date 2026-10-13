import type { CategoryKey } from "./categories";

export type GeoWindow = "24h" | "7d" | "30d";

export const GEO_WINDOWS: { label: string; value: GeoWindow }[] = [
  { label: "24 小时", value: "24h" },
  { label: "7 天", value: "7d" },
  { label: "30 天", value: "30d" },
];

export function windowLabel(value: GeoWindow): string {
  return GEO_WINDOWS.find((item) => item.value === value)?.label ?? value;
}

// 热度分档：浅 → 深；分档算法在 utils/geo.ts
export const HEAT_COLORS = ["#e8eefb", "#cfe0fb", "#a9c8f5", "#7aa7ec", "#4a80dd", "#2563eb"];
export const EMPTY_AREA_COLOR = "#eef1f6";
export const SELECTED_AREA_COLOR = "#fdd9a0";

// 同一地区最多 4 个点：按板块固定偏移，避免坐标完全重叠
export const CATEGORY_OFFSETS: Record<CategoryKey, [number, number]> = {
  politics: [0, 0],
  economy: [0.75, 0.75],
  finance: [-0.75, 0.75],
  military: [0.75, -0.75],
};

export const POINT_SIZE = { min: 5, max: 14 } as const;

export const GEO_TEXT = {
  empty: "暂无地理标注数据，请先执行采集任务",
  untagged: (count: number) => `未定位 ${count} 条`,
  rankingTitle: "地区榜",
  backToRanking: "← 返回地区榜",
  regionTitle: (name: string, window: GeoWindow) => `${name} · 近 ${windowLabel(window)}`,
  legendHint: "点击图例可只看某一类",
} as const;
