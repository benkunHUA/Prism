import { Card, Select, Space, Table, Tag } from "antd";
import { useMemo, useState } from "react";

import { api } from "../api/endpoints";
import type { SnapshotItem } from "../api/types";
import ArticleList from "../components/ArticleList";
import PageHeader from "../components/PageHeader";
import ReportPanel from "../components/ReportPanel";
import TimelineList from "../components/TimelineList";
import { CATEGORY_MAP } from "../constants/categories";
import { ASSET_CLASSES, TEXT } from "../constants/options";
import { useAsync } from "../hooks/useAsync";
import { changeClass, formatChangePct, formatDateTime } from "../utils/format";

const META = CATEGORY_MAP.finance;
const FINANCE_SUBTYPES = ["市场异动", "融资/IPO/并购", "监管动态", "公司重大事件", "资金与流动性"];

export default function FinancePage() {
  const [assetClass, setAssetClass] = useState<string | undefined>(undefined);
  const snapshots = useAsync(() => api.snapshots({ asset_class: assetClass }), [assetClass]);
  const timeline = useAsync(() => api.timeline("finance"), []);

  const items = snapshots.data?.items ?? [];
  const batchId = items[0]?.batch_id ?? null;
  const capturedAt = items[0]?.captured_at ?? null;

  const compare = useMemo(() => {
    const batches: string[] = [];
    for (const item of items) {
      if (item.batch_id && !batches.includes(item.batch_id)) batches.push(item.batch_id);
      if (batches.length >= 2) break;
    }
    const latest = new Map<string, SnapshotItem>();
    const previous = new Map<string, SnapshotItem>();
    for (const item of items) {
      if (item.batch_id === batches[0]) latest.set(item.asset_name, item);
      else if (batches[1] && item.batch_id === batches[1]) previous.set(item.asset_name, item);
    }
    return { latest: Array.from(latest.values()), previous };
  }, [items]);

  const columns = [
    { title: "类别", dataIndex: "asset_class", key: "asset_class" },
    { title: "资产", dataIndex: "asset_name", key: "asset_name" },
    {
      title: "价格",
      key: "price",
      render: (_: unknown, row: SnapshotItem) => row.price ?? "—",
    },
    {
      title: "本批次涨跌",
      key: "change_pct",
      render: (_: unknown, row: SnapshotItem) => (
        <span className={changeClass(row.change_pct)}>{formatChangePct(row.change_pct)}</span>
      ),
    },
    {
      title: "较上轮",
      key: "previous",
      render: (_: unknown, row: SnapshotItem) => {
        const prev = compare.previous.get(row.asset_name);
        if (!prev) return <span className="aurora-muted">—</span>;
        const delta =
          row.change_pct !== null && prev.change_pct !== null ? row.change_pct - prev.change_pct : null;
        return (
          <Space size={6}>
            <span className={changeClass(prev.change_pct)}>{formatChangePct(prev.change_pct)}</span>
            <span className="aurora-muted">
              {delta === null ? "" : `(${delta >= 0 ? "+" : ""}${delta.toFixed(2)}pp)`}
            </span>
          </Space>
        );
      },
    },
  ];

  return (
    <div className="aurora-stack">
      <PageHeader title={`${META.label}板块`} tagline={META.tagline} />
      <ReportPanel category="finance" />

      <Card
        size="small"
        title="市场快照"
        loading={snapshots.loading}
        variant="outlined"
        extra={
          <Space size={8}>
            {batchId ? <span className="aurora-muted">批次 {batchId} · {formatDateTime(capturedAt)}</span> : null}
            <Select
              allowClear
              size="small"
              placeholder="按资产类别筛选"
              style={{ width: 160 }}
              value={assetClass}
              onChange={setAssetClass}
              options={ASSET_CLASSES}
            />
          </Space>
        }
      >
        <Table
          size="small"
          rowKey="id"
          dataSource={compare.latest}
          columns={columns}
          pagination={{ pageSize: 12, hideOnSinglePage: true }}
          locale={{ emptyText: TEXT.emptySnapshots }}
        />
      </Card>

      <Card size="small" title="驱动事件归因" loading={timeline.loading} variant="outlined">
        <TimelineList
          items={timeline.data?.items ?? []}
          emptyText={TEXT.emptyTimeline(META.label)}
          subtitleOptions={FINANCE_SUBTYPES}
        />
      </Card>
      <Tag color="gold">涨跌配色遵循国内习惯：红涨绿跌</Tag>
      <ArticleList category="finance" />
    </div>
  );
}
