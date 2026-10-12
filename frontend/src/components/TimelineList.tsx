import { Card, Select, Space, Tag, Timeline } from "antd";
import { useMemo, useState } from "react";

import type { TimelineEvent } from "../api/types";
import { IMPORTANCE_COLORS, TEXT } from "../constants/options";
import { formatDateTime } from "../utils/format";

import EmptyHint from "./EmptyHint";

interface Props {
  items: TimelineEvent[];
  emptyText?: string;
  subtitleOptions?: string[];
}

export default function TimelineList({ items, emptyText, subtitleOptions = [] }: Props) {
  const [subtype, setSubtype] = useState<string | undefined>(undefined);

  const visible = useMemo(
    () => (subtype ? items.filter((item) => item.subtype === subtype) : items),
    [items, subtype],
  );

  const options = subtitleOptions.length
    ? subtitleOptions
    : Array.from(new Set(items.map((item) => item.subtype))).filter(Boolean);

  if (!items.length) {
    return <EmptyHint text={emptyText ?? TEXT.emptyDefault} compact />;
  }

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={8}>
      {options.length > 1 ? (
        <Select
          allowClear
          size="small"
          placeholder="按子类型筛选"
          style={{ width: 200 }}
          value={subtype}
          onChange={setSubtype}
          options={options.map((item) => ({ label: item, value: item }))}
        />
      ) : null}
      <Timeline
        items={visible.map((event) => ({
          color: event.importance === "high" ? "red" : "blue",
          children: (
            <Card size="small" variant="outlined">
              <Space size={6} wrap style={{ marginBottom: 4 }}>
                <Tag color="geekblue">{event.subtype}</Tag>
                {event.actor ? <span className="aurora-muted">{event.actor}</span> : null}
                {event.region ? <span className="aurora-muted">· {event.region}</span> : null}
                <span className="aurora-muted">· {formatDateTime(event.occurred_at)}</span>
                <Tag color={IMPORTANCE_COLORS[event.importance] ?? "default"}>
                  {event.importance === "high" ? "高" : event.importance === "low" ? "低" : "中"}
                </Tag>
              </Space>
              <div>{event.summary}</div>
            </Card>
          ),
        }))}
      />
    </Space>
  );
}
