import { Card, Col, Row, Space, Tag } from "antd";
import { useMemo } from "react";

import { api } from "../api/endpoints";
import type { StanceItem } from "../api/types";
import ArticleList from "../components/ArticleList";
import EmptyHint from "../components/EmptyHint";
import PageHeader from "../components/PageHeader";
import ReportPanel from "../components/ReportPanel";
import TimelineList from "../components/TimelineList";
import { CATEGORY_MAP } from "../constants/categories";
import { STANCE_TOPICS, TEXT, TONE_COLORS } from "../constants/options";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime } from "../utils/format";

const META = CATEGORY_MAP.politics;

export default function PoliticsPage() {
  const timeline = useAsync(() => api.timeline("politics"), []);
  const stances = useAsync(() => api.stances(), []);

  const grouped = useMemo(() => {
    const map = new Map<string, StanceItem[]>();
    for (const stance of stances.data?.items ?? []) {
      const list = map.get(stance.topic) ?? [];
      list.push(stance);
      map.set(stance.topic, list);
    }
    return Array.from(map.entries());
  }, [stances.data]);

  return (
    <div className="aurora-stack">
      <PageHeader title={`${META.label}板块`} tagline={META.tagline} />
      <ReportPanel category="politics" />
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card size="small" title="政治事件时间线" loading={timeline.loading} variant="outlined">
            <TimelineList
              items={timeline.data?.items ?? []}
              emptyText={TEXT.emptyTimeline(META.label)}
              subtitleOptions={["选举/组阁", "立法与投票", "外交与峰会", "制裁与出口管制", "条约与协议", "安全战略声明"]}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card size="small" title="议题立场追踪" loading={stances.loading} variant="outlined">
            {grouped.length === 0 ? (
              <EmptyHint text={TEXT.emptyStances} compact />
            ) : (
              <Space direction="vertical" size={10} style={{ width: "100%" }}>
                {grouped.map(([topic, list]) => (
                  <Card key={topic} size="small" type="inner" title={topic}>
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      {list.map((stance) => (
                        <div key={stance.id}>
                          <Space size={6} wrap>
                            <span>{stance.actor}</span>
                            <Tag color={TONE_COLORS[stance.tone] ?? "default"}>{stance.tone}</Tag>
                            <span className="aurora-muted">{formatDateTime(stance.stated_at)}</span>
                          </Space>
                          <div>{stance.stance_text}</div>
                        </div>
                      ))}
                    </Space>
                  </Card>
                ))}
              </Space>
            )}
            <div style={{ marginTop: 8 }} className="aurora-muted">
              追踪议题：{STANCE_TOPICS.map((item) => item.label).join(" / ")}
            </div>
          </Card>
        </Col>
      </Row>
      <ArticleList category="politics" />
    </div>
  );
}
