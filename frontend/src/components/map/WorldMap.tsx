import { MapChart, ScatterChart } from "echarts/charts";
import { GeoComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef } from "react";

import type { GeoRegion } from "../../api/types";
import worldGeo from "../../assets/world.geo.json";
import { CATEGORY_MAP } from "../../constants/categories";
import type { CategoryKey } from "../../constants/categories";
import { EMPTY_AREA_COLOR, SELECTED_AREA_COLOR } from "../../constants/geo";
import { MAP_BOARD_STYLE, MAP_BOARD_TEXT } from "../../constants/mapBoard";
import { buildHeatScale, pointSize, regionPoints } from "../../utils/geo";

echarts.use([MapChart, ScatterChart, GeoComponent, TooltipComponent, CanvasRenderer]);
echarts.registerMap("world", worldGeo as never);

/** 底图要素名即地区 code；每次全量下发，避免合并更新后留下旧配色。 */
const REGION_CODES: string[] = (
  worldGeo as unknown as { features: { properties: { name: string } }[] }
).features.map((feature) => feature.properties.name);

interface Props {
  regions: GeoRegion[];
  categories: string[];
  selected: string | null;
  onSelect: (code: string) => void;
  loading?: boolean;
}

/** ECharts 散点数据项：name 用唯一 key，避免同地区多板块点重名。 */
interface ScatterDatum {
  key: string;
  code: string;
  regionName: string;
  category: string;
  count: number;
  name: string;
  value: [number, number, number];
  itemStyle: { color: string };
}

interface ChartParams {
  seriesType?: string;
  name?: string;
  data?: unknown;
}

function categoryLabel(key: string): string {
  return CATEGORY_MAP[key as CategoryKey]?.label ?? key;
}

function categoryColor(key: string): string {
  return CATEGORY_MAP[key as CategoryKey]?.color ?? MAP_BOARD_STYLE.fallbackColor;
}

export default function WorldMap({
  regions,
  categories,
  selected,
  onSelect,
  loading = false,
}: Props) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ReturnType<typeof echarts.init> | null>(null);
  const handlerRef = useRef(onSelect);
  const visibleRef = useRef<Set<string>>(new Set());
  handlerRef.current = onSelect;
  visibleRef.current = new Set(regions.map((region) => region.code));

  const option = useMemo(() => {
    const heat = buildHeatScale(regions.map((region) => region.count));
    const max = Math.max(1, ...regions.map((region) => region.count));
    const regionByCode = new Map(regions.map((region) => [region.code, region]));
    const points: ScatterDatum[] = regionPoints(regions, categories).map((point) => ({
      ...point,
      name: point.key,
      value: [point.lng, point.lat, point.count],
      itemStyle: { color: categoryColor(point.category) },
    }));

    return {
      tooltip: {
        trigger: "item" as const,
        formatter: (params: ChartParams) => {
          if (params.seriesType === "scatter") {
            const point = params.data as ScatterDatum | undefined;
            return point
              ? MAP_BOARD_TEXT.pointTooltip(
                  point.regionName,
                  categoryLabel(point.category),
                  point.count,
                )
              : "";
          }
          const region = regionByCode.get(params.name ?? "");
          return region ? MAP_BOARD_TEXT.areaTooltip(region.name, region.count) : "";
        },
      },
      geo: {
        map: "world",
        roam: true,
        itemStyle: {
          areaColor: EMPTY_AREA_COLOR,
          borderColor: MAP_BOARD_STYLE.borderColor,
          borderWidth: MAP_BOARD_STYLE.borderWidth,
        },
        emphasis: {
          itemStyle: { areaColor: MAP_BOARD_STYLE.hoverAreaColor },
          label: { show: false },
        },
        select: { disabled: true },
        // geo 组件的区域配色只认 geo.regions，map series 的 data.itemStyle 不参与绘制
        regions: REGION_CODES.map((code) => {
          const region = regionByCode.get(code);
          return {
            name: code,
            itemStyle: {
              areaColor: !region
                ? EMPTY_AREA_COLOR
                : code === selected
                  ? SELECTED_AREA_COLOR
                  : heat(region.count),
            },
          };
        }),
      },
      series: [
        {
          type: "map" as const,
          geoIndex: 0,
          data: regions.map((region) => ({ name: region.code, value: region.count })),
        },
        {
          type: "scatter" as const,
          coordinateSystem: "geo" as const,
          // 关掉散点动画：默认入场动画的前几帧 opacity 为 0，取帧时看着像「有底图没有点」
          animation: false as const,
          symbolSize: (value: number[]) => pointSize(value[2], max),
          itemStyle: {
            opacity: MAP_BOARD_STYLE.pointOpacity,
            borderColor: MAP_BOARD_STYLE.pointBorderColor,
            borderWidth: MAP_BOARD_STYLE.pointBorderWidth,
          },
          data: points,
        },
      ],
    };
  }, [regions, categories, selected]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const chart = echarts.init(host);
    chartRef.current = chart;
    chart.on("click", (params: ChartParams) => {
      const point = params.data as ScatterDatum | undefined;
      const code = params.seriesType === "scatter" ? point?.code : params.name;
      if (code && visibleRef.current.has(code)) handlerRef.current(code);
    });
    const resize = () => chart.resize();
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    window.addEventListener("resize", resize);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", resize);
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option);
  }, [option]);

  return (
    <div style={{ position: "relative", height: MAP_BOARD_STYLE.height }}>
      <div ref={hostRef} style={{ width: "100%", height: "100%" }} />
      {loading ? (
        <span className="aurora-muted" style={{ position: "absolute", top: 8, left: 8 }}>
          {MAP_BOARD_TEXT.loading}
        </span>
      ) : null}
    </div>
  );
}
