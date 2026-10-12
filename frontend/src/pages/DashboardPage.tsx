import { Card, Col, Row, Space, Tag, Typography } from "antd";
import { Link } from "react-router-dom";

import { api } from "../api/endpoints";
import EmptyHint from "../components/EmptyHint";
import PageHeader from "../components/PageHeader";
import StatCards from "../components/StatCards";
import { CATEGORIES } from "../constants/categories";
import type { CategoryKey } from "../constants/categories";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime, formatNumber } from "../utils/format";

export default function DashboardPage() {
  const dashboard = useAsync(() => api.dashboard(), []);
  const categories = useAsync(() => api.categories(), []);
  const weapons = useAsync(() => api.weapons(), []);
  const indicators = useAsync(() => api.indicators(), []);
  const snapshots = useAsync(() => api.snapshots(), []);
  const moderations = useAsync(() => api.moderations(), []);

  const summary = dashboard.data;
  const overview = new Map((categories.data ?? []).map((item) => [item.category, item]));
  const weaponItems = weapons.data?.items ?? [];
  const indicatorItems = indicators.data?.items ?? [];
  const snapshotItems = snapshots.data?.items ?? [];
  const moderationItems = moderations.data?.items ?? [];

  const latestBatch = snapshotItems[0]?.batch_id ?? null;
  const batchItems = latestBatch
    ? snapshotItems.filter((item) => item.batch_id === latestBatch)
    : snapshotItems;
  const rising = batchItems.filter((item) => (item.change_pct ?? 0) >= 0).length;
  const falling = batchItems.length - rising;
  const latestIndicator = indicatorItems[0] ?? null;

  function boardHint(key: CategoryKey): string {
    switch (key) {
      case "politics": {
        const stanceDrafts = moderationItems.filter((item) => item.type === "stance").length;
        return `待确认立场 ${stanceDrafts} 条`;
      }
      case "military": {
        const weaponDrafts = moderationItems.filter((item) => item.type === "weapon").length;
        return `武器档案 ${weaponItems.length} 条 · 待确认 ${weaponDrafts} 条`;
      }
      case "economy":
        return latestIndicator
          ? `最新指标 ${latestIndicator.region} ${latestIndicator.indicator} = ${formatNumber(
              latestIndicator.value,
              latestIndicator.unit ?? "",
            )}`
          : "暂无指标数据";
      case "finance":
        return batchItems.length
          ? `最新批次 ${batchItems.length} 个资产 · 涨 ${rising} / 跌 ${falling}`
          : "暂无行情快照";
      default:
        return "";
    }
  }

  return (
    <div className="aurora-stack">
      <PageHeader
        title="仪表盘"
        tagline="全球政治 · 经济 · 金融 · 军事信息收集与分析"
      />

      <StatCards
        items={[
          { label: "今日新增文章", value: summary?.today_articles ?? 0 },
          { label: "今日生成分析", value: summary?.today_analyses ?? 0 },
          {
            label: "源健康",
            value: summary ? `${summary.source_health.healthy}/${summary.source_health.enabled}` : "—",
            hint: "健康 / 启用",
          },
          {
            label: "下次定时任务",
            value: summary?.next_run_at ? formatDateTime(summary.next_run_at) : "未排期",
          },
        ]}
      />

      {dashboard.error ? <EmptyHint text={`后端不可用：${dashboard.error}`} compact /> : null}

      <Row gutter={[12, 12]}>
        {CATEGORIES.map((category) => {
          const item = overview.get(category.key);
          return (
            <Col xs={24} md={12} key={category.key}>
              <Card
                size="small"
                variant="outlined"
                title={
                  <Space size={8}>
                    <Tag color={category.color}>{category.label}</Tag>
                    <span className="aurora-muted">{category.tagline}</span>
                  </Space>
                }
                extra={<Link to={category.path}>进入 →</Link>}
              >
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                  <Typography.Text strong>{category.dailyTitle}</Typography.Text>
                  <div>
                    {item?.latest_daily_title ? (
                      <Typography.Text>{item.latest_daily_title}</Typography.Text>
                    ) : (
                      <span className="aurora-muted">今日报告尚未生成</span>
                    )}
                  </div>
                  <span className="aurora-muted">
                    近 24 小时新增 {item?.article_count ?? 0} 篇 · {boardHint(category.key)}
                  </span>
                </Space>
              </Card>
            </Col>
          );
        })}
      </Row>
    </div>
  );
}
