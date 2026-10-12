import { Card, Col, Row, Select, Space, Tag } from "antd";
import { useMemo, useState } from "react";

import { api } from "../api/endpoints";
import ArticleList from "../components/ArticleList";
import EmptyHint from "../components/EmptyHint";
import PageHeader from "../components/PageHeader";
import ReportPanel from "../components/ReportPanel";
import StatCards from "../components/StatCards";
import TimelineList from "../components/TimelineList";
import { CATEGORY_MAP } from "../constants/categories";
import { LIFECYCLE_COLORS, TEXT, WEAPON_LIFECYCLE } from "../constants/options";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime } from "../utils/format";

const META = CATEGORY_MAP.military;
const CONFLICT_SUBTYPES = ["冲突进展", "停火与和谈", "军事行动", "袭击与损失"];

export default function MilitaryPage() {
  const [lifecycle, setLifecycle] = useState<string | undefined>(undefined);

  const timeline = useAsync(() => api.timeline("military"), []);
  const weapons = useAsync(() => api.weapons(lifecycle), [lifecycle]);
  const moderations = useAsync(() => api.moderations("military"), []);

  const events = timeline.data?.items ?? [];
  const weaponItems = weapons.data?.items ?? [];
  const weaponDrafts = (moderations.data?.items ?? []).filter((item) => item.type === "weapon").length;

  const frontLines = useMemo(() => {
    const map = new Map<string, typeof events>();
    for (const event of events) {
      const key = event.group_key || event.region || "未标注战线";
      const list = map.get(key) ?? [];
      list.push(event);
      map.set(key, list);
    }
    return Array.from(map.entries());
  }, [events]);

  return (
    <div className="aurora-stack">
      <PageHeader title={`${META.label}板块`} tagline={META.tagline} />
      <StatCards
        items={[
          { label: "武器档案", value: weaponItems.length },
          { label: "活跃战线", value: frontLines.length },
          { label: "冲突事件", value: events.length },
          { label: "待确认", value: weaponDrafts, hint: "武器条目" },
        ]}
      />
      <ReportPanel category="military" />

      <Card size="small" title="冲突态势（按战线）" loading={timeline.loading} variant="outlined">
        {frontLines.length === 0 ? (
          <EmptyHint text={TEXT.emptyTimeline(META.label)} compact />
        ) : (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            {frontLines.map(([line, list]) => (
              <Card
                key={line}
                size="small"
                type="inner"
                title={
                  <Space size={8}>
                    <span>{line}</span>
                    <Tag>{list.length} 条进展</Tag>
                  </Space>
                }
              >
                <TimelineList items={list} emptyText={TEXT.emptyTimeline(META.label)} />
              </Card>
            ))}
          </Space>
        )}
      </Card>

      <Card
        size="small"
        title="武器装备动态"
        loading={weapons.loading}
        variant="outlined"
        extra={
          <Select
            allowClear
            size="small"
            placeholder="按生命周期筛选"
            style={{ width: 170 }}
            value={lifecycle}
            onChange={setLifecycle}
            options={WEAPON_LIFECYCLE}
          />
        }
      >
        {weaponItems.length === 0 ? (
          <EmptyHint text={TEXT.emptyWeapons} compact />
        ) : (
          <div className="aurora-grid-cards">
            {weaponItems.map((weapon) => (
              <Card key={weapon.id} size="small" type="inner">
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                  <Space size={6} wrap>
                    <strong>{weapon.name}</strong>
                    <Tag color={LIFECYCLE_COLORS[weapon.lifecycle_status] ?? "default"}>
                      {weapon.lifecycle_status}
                    </Tag>
                    {weapon.verification_status !== "confirmed" ? <Tag color="orange">待确认</Tag> : null}
                  </Space>
                  <span className="aurora-muted">
                    {weapon.origin || "国别未知"} · {weapon.weapon_type || "类型未知"} · 首次发现{" "}
                    {formatDateTime(weapon.first_seen_at)}
                  </span>
                  {weapon.params_text ? <div>{weapon.params_text}</div> : null}
                </Space>
              </Card>
            ))}
          </div>
        )}
      </Card>

      <Row gutter={[16, 16]}>
        <Col span={24}>
          <ArticleList category="military" />
        </Col>
      </Row>
      <span className="aurora-muted">冲突子类型：{CONFLICT_SUBTYPES.join(" / ")}</span>
    </div>
  );
}
