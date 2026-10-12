import { Card, Col, Row } from "antd";
import { useMemo, useState } from "react";

import { api } from "../api/endpoints";
import EmptyHint from "../components/EmptyHint";
import PageHeader from "../components/PageHeader";
import StatCards from "../components/StatCards";
import CategoryStrip from "../components/map/CategoryStrip";
import MapLegend from "../components/map/MapLegend";
import RegionPanel from "../components/map/RegionPanel";
import WorldMap from "../components/map/WorldMap";
import { CATEGORIES } from "../constants/categories";
import type { GeoWindow } from "../constants/geo";
import { MAP_BOARD_STYLE } from "../constants/mapBoard";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime } from "../utils/format";
import { filterRegions } from "../utils/geo";

const ALL_CATEGORY_KEYS = CATEGORIES.map((category) => category.key);

export default function MapBoardPage() {
  const [windowKey, setWindowKey] = useState<GeoWindow>("24h");
  const [selected, setSelected] = useState<string | null>(null);
  const [activeCategories, setActiveCategories] = useState<string[]>(ALL_CATEGORY_KEYS);

  const dashboard = useAsync(() => api.dashboard(), []);
  const overview = useAsync(() => api.categories(), []);
  const geo = useAsync(() => api.geo(windowKey), [windowKey]);

  const summary = dashboard.data;
  const visibleRegions = useMemo(
    () => filterRegions(geo.data?.regions ?? [], activeCategories),
    [geo.data, activeCategories],
  );

  function toggleCategory(key: string) {
    setActiveCategories((current) => {
      const next = current.includes(key)
        ? current.filter((item) => item !== key)
        : [...current, key];
      return next.length === 0 ? current : next;
    });
  }

  function changeWindow(value: GeoWindow) {
    setWindowKey(value);
    setSelected(null);
  }

  return (
    <div className="aurora-stack">
      <PageHeader
        title="世界看板"
        tagline="全球政治 · 经济 · 金融 · 军事信息收集与分析"
      />
      <StatCards
        items={[
          { label: "今日新增文章", value: summary?.today_articles ?? 0 },
          { label: "今日生成分析", value: summary?.today_analyses ?? 0 },
          {
            label: "源健康",
            value: summary
              ? `${summary.source_health.healthy}/${summary.source_health.enabled}`
              : "—",
            hint: "健康 / 启用",
          },
          {
            label: "下次定时任务",
            value: summary?.next_run_at ? formatDateTime(summary.next_run_at) : "未排期",
          },
        ]}
      />
      {dashboard.error ? <EmptyHint text={`后端不可用：${dashboard.error}`} compact /> : null}
      <CategoryStrip overview={overview.data ?? []} />
      <MapLegend
        windowKey={windowKey}
        onWindowChange={changeWindow}
        activeCategories={activeCategories}
        onToggleCategory={toggleCategory}
        untagged={geo.data?.untagged ?? 0}
      />
      <Row gutter={[12, 12]}>
        <Col xs={24} lg={16}>
          <Card
            size="small"
            variant="outlined"
            styles={{ body: { padding: MAP_BOARD_STYLE.mapPadding } }}
          >
            <WorldMap
              regions={visibleRegions}
              categories={activeCategories}
              selected={selected}
              onSelect={setSelected}
              loading={geo.loading}
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <RegionPanel
            regions={visibleRegions}
            windowKey={windowKey}
            selected={selected}
            onSelect={setSelected}
            loading={geo.loading}
          />
        </Col>
      </Row>
    </div>
  );
}
