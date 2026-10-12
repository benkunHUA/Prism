// 看板地图组件的展示常量：尺寸、配色、文案（地区语义常量见 constants/geo.ts）
export const MAP_BOARD_STYLE = {
  height: 520,
  borderColor: "#dbe2ee",
  borderWidth: 0.5,
  hoverAreaColor: "#c7dbf8",
  pointOpacity: 0.8,
  pointBorderColor: "#fff",
  pointBorderWidth: 0.6,
  fallbackColor: "#64748b",
  stripPadding: 10,
} as const;

export const CHIP_STYLE = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  fontSize: 13,
} as const;

export const CHIP_MARK_STYLE = {
  width: 10,
  height: 10,
  display: "inline-block",
} as const;

export const CHIP_DIMMED_OPACITY = 0.35;
export const CHIP_CIRCLE_RADIUS = "50%";
export const CHIP_SQUARE_RADIUS = 3;

export const MAP_BOARD_TEXT = {
  loading: "加载中…",
  areaTooltip: (name: string, count: number) => `${name}<br/>共 ${count} 条`,
  pointTooltip: (regionName: string, label: string, count: number) =>
    `${regionName}<br/>${label} · ${count} 条`,
  regionEmpty: "该地区在时间窗内没有文章",
  unknownSource: "未知来源",
  stripCount: (count: number) => `近 24h ${count} 篇`,
  stripPending: (label: string) => `${label}今日报告尚未生成`,
} as const;
