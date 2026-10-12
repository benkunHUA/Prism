import type { GeoRegion } from "../api/types";
import { CATEGORY_OFFSETS, HEAT_COLORS, POINT_SIZE } from "../constants/geo";

export interface MapPoint {
  code: string;
  name: string;
  category: string;
  count: number;
  lng: number;
  lat: number;
}

export function countFor(region: GeoRegion, categories: string[]): number {
  return categories.reduce((sum, key) => sum + (region.by_category[key] ?? 0), 0);
}

/** 按所选板块重算 count，并丢掉重算后为 0 的地区。 */
export function filterRegions(regions: GeoRegion[], categories: string[]): GeoRegion[] {
  return regions
    .map((region) => ({ ...region, count: countFor(region, categories) }))
    .filter((region) => region.count > 0);
}

/** 按不同数值的排名分档，避免单个超热地区把其余国家压成最浅一档。 */
export function buildHeatScale(counts: number[]): (count: number) => string {
  const distinct = Array.from(new Set(counts.filter((count) => count > 0))).sort((a, b) => a - b);
  if (distinct.length === 0) return () => HEAT_COLORS[0];
  if (distinct.length === 1) return () => HEAT_COLORS[Math.floor(HEAT_COLORS.length / 2)];
  const step = HEAT_COLORS.length - 1;
  return (count: number) => {
    if (count <= 0) return HEAT_COLORS[0];
    const index = distinct.indexOf(count);
    if (index < 0) return HEAT_COLORS[HEAT_COLORS.length - 1];
    return HEAT_COLORS[Math.round((index / (distinct.length - 1)) * step)];
  };
}

/** 把「地区 × 板块」展开成散点：同地区不同板块坐标做固定偏移。 */
export function regionPoints(regions: GeoRegion[], categories: string[]): MapPoint[] {
  const points: MapPoint[] = [];
  for (const region of regions) {
    for (const key of categories) {
      const count = region.by_category[key] ?? 0;
      if (count <= 0) continue;
      const offset = CATEGORY_OFFSETS[key as keyof typeof CATEGORY_OFFSETS] ?? [0, 0];
      points.push({
        code: region.code,
        name: region.name,
        category: key,
        count,
        lng: region.lng + offset[0],
        lat: region.lat + offset[1],
      });
    }
  }
  return points;
}

export function pointSize(count: number, max: number): number {
  if (max <= 1) return POINT_SIZE.min;
  const ratio = Math.min(1, Math.max(0, count / max));
  return POINT_SIZE.min + ratio * (POINT_SIZE.max - POINT_SIZE.min);
}
