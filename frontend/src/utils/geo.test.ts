import { describe, expect, it } from "vitest";

import type { GeoRegion } from "../api/types";
import { HEAT_COLORS } from "../constants/geo";
import { buildHeatScale, countFor, filterRegions, pointSize, regionPoints } from "./geo";

function region(code: string, byCategory: Record<string, number>): GeoRegion {
  return {
    code,
    name: code,
    lng: 10,
    lat: 20,
    count: Object.values(byCategory).reduce((sum, value) => sum + value, 0),
    by_category: { politics: 0, economy: 0, finance: 0, military: 0, ...byCategory },
  };
}

describe("countFor / filterRegions", () => {
  it("只累计被选中的板块", () => {
    const item = region("il", { politics: 3, military: 6, finance: 1 });
    expect(countFor(item, ["politics", "military"])).toBe(9);
    expect(countFor(item, ["economy"])).toBe(0);
  });

  it("筛选后 count 用重算值，为 0 的地区被丢掉", () => {
    const filtered = filterRegions([region("il", { military: 6 }), region("us", { finance: 2 })],
                                  ["military"]);
    expect(filtered.map((item) => item.code)).toEqual(["il"]);
    expect(filtered[0].count).toBe(6);
  });
});

describe("buildHeatScale", () => {
  it("只有一种数值时返回中间档，空数组返回最浅档", () => {
    expect(buildHeatScale([4, 4])(4)).toBe(HEAT_COLORS[Math.floor(HEAT_COLORS.length / 2)]);
    expect(buildHeatScale([])(3)).toBe(HEAT_COLORS[0]);
  });

  it("按数值排名分档，单个超热地区不会把其余压成最浅档", () => {
    const scale = buildHeatScale([1, 1, 1, 1, 10]);
    expect(scale(1)).toBe(HEAT_COLORS[0]);
    expect(scale(10)).toBe(HEAT_COLORS[HEAT_COLORS.length - 1]);
  });

  it("中间值落在中间档", () => {
    const scale = buildHeatScale([1, 2, 3, 4, 5]);
    expect(scale(3)).toBe(HEAT_COLORS[Math.round((2 / 4) * (HEAT_COLORS.length - 1))]);
  });
});

describe("regionPoints", () => {
  it("按板块逐地区展开，只保留有量的板块并做偏移", () => {
    const points = regionPoints([region("il", { politics: 3, military: 6 })],
                                ["politics", "economy", "finance", "military"]);
    expect(points.map((point) => point.category)).toEqual(["politics", "military"]);
    expect(points[0]).toMatchObject({ code: "il", count: 3 });
    expect(points[1].lng).not.toBe(points[0].lng);
  });
});

describe("pointSize", () => {
  it("把条数线性映射到最小与最大之间", () => {
    expect(pointSize(0, 10)).toBe(5);
    expect(pointSize(10, 10)).toBe(14);
    expect(pointSize(5, 10)).toBeGreaterThan(5);
    expect(pointSize(3, 1)).toBe(5);
  });
});
