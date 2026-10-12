import { Card, Select, Space, Table, Tag } from "antd";
import { useMemo, useState } from "react";

import { api } from "../api/endpoints";
import type { IndicatorItem } from "../api/types";
import ArticleList from "../components/ArticleList";
import PageHeader from "../components/PageHeader";
import ReportPanel from "../components/ReportPanel";
import TimelineList from "../components/TimelineList";
import { CATEGORY_MAP } from "../constants/categories";
import { TEXT, VERDICT_LABELS } from "../constants/options";
import { useAsync } from "../hooks/useAsync";
import { compareToForecast, formatDateTime, formatNumber } from "../utils/format";

const META = CATEGORY_MAP.economy;
const POLICY_SUBTYPES = ["货币政策", "财政政策", "贸易政策", "产业政策", "监管与改革"];

export default function EconomyPage() {
  const [region, setRegion] = useState<string | undefined>(undefined);
  const indicators = useAsync(() => api.indicators({ region }), [region]);
  const timeline = useAsync(() => api.timeline("economy"), []);

  const rows = indicators.data?.items ?? [];
  const regionOptions = useMemo(
    () => Array.from(new Set(rows.map((item) => item.region))).filter(Boolean),
    [rows],
  );

  const columns = [
    { title: "指标", dataIndex: "indicator", key: "indicator" },
    { title: "地区", dataIndex: "region", key: "region" },
    { title: "周期", dataIndex: "period", key: "period" },
    {
      title: "数值",
      key: "value",
      render: (_: unknown, row: IndicatorItem) => formatNumber(row.value, row.unit ?? ""),
    },
    {
      title: "前值",
      key: "previous",
      render: (_: unknown, row: IndicatorItem) => formatNumber(row.previous, row.unit ?? ""),
    },
    {
      title: "预期",
      key: "forecast",
      render: (_: unknown, row: IndicatorItem) => formatNumber(row.forecast, row.unit ?? ""),
    },
    {
      title: "vs 预期",
      key: "verdict",
      render: (_: unknown, row: IndicatorItem) => {
        const verdict = VERDICT_LABELS[compareToForecast(row.value, row.forecast)];
        return <Tag color={verdict.color}>{verdict.text}</Tag>;
      },
    },
    {
      title: "发布时间",
      key: "released_at",
      render: (_: unknown, row: IndicatorItem) => formatDateTime(row.released_at),
    },
  ];

  return (
    <div className="aurora-stack">
      <PageHeader title={`${META.label}板块`} tagline={META.tagline} />
      <ReportPanel category="economy" />

      <Card
        size="small"
        title="最新宏观指标"
        loading={indicators.loading}
        variant="outlined"
        extra={
          <Select
            allowClear
            size="small"
            placeholder="按地区筛选"
            style={{ width: 150 }}
            value={region}
            onChange={setRegion}
            options={regionOptions.map((item) => ({ label: item, value: item }))}
          />
        }
      >
        <Table
          size="small"
          rowKey="id"
          dataSource={rows}
          columns={columns}
          pagination={{ pageSize: 10, hideOnSinglePage: true }}
          locale={{ emptyText: TEXT.emptyIndicators }}
        />
      </Card>

      <Card size="small" title="政策事件流" loading={timeline.loading} variant="outlined">
        <TimelineList
          items={timeline.data?.items ?? []}
          emptyText={TEXT.emptyTimeline(META.label)}
          subtitleOptions={POLICY_SUBTYPES}
        />
      </Card>

      <Space className="aurora-muted">政策子类型：{POLICY_SUBTYPES.join(" / ")}</Space>
      <ArticleList category="economy" />
    </div>
  );
}
