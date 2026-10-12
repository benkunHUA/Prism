import { Button, Card, Drawer, List, Space, Tag, Typography } from "antd";
import { useState } from "react";

import { api } from "../api/endpoints";
import { CATEGORY_MAP } from "../constants/categories";
import { TEXT } from "../constants/options";
import type { CategoryKey } from "../constants/categories";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime } from "../utils/format";

import EmptyHint from "./EmptyHint";
import MarkdownView from "./MarkdownView";

interface Props {
  category: CategoryKey;
  kind?: "daily" | "brief";
}

export default function ReportPanel({ category, kind = "daily" }: Props) {
  const meta = CATEGORY_MAP[category];
  const [open, setOpen] = useState(false);

  const { data, loading } = useAsync(() => api.categoryAnalyses(category, kind), [category, kind]);
  const latest = data?.items?.[0] ?? null;

  const detail = useAsync(
    () => (latest ? api.analysis(latest.id) : Promise.resolve(null)),
    [latest?.id],
  );
  const analysis = detail.data;

  const excerpt = analysis?.content_md
    ? analysis.content_md.replace(/[#*>`\-]/g, "").replace(/\s+/g, " ").slice(0, 140)
    : "";

  return (
    <Card
      size="small"
      variant="outlined"
      loading={loading}
      title={
        <Space size={8}>
          <Tag color="blue">{kind === "daily" ? "今日报告" : "最新快讯"}</Tag>
          <span>{meta.dailyTitle}</span>
        </Space>
      }
      extra={
        latest ? (
          <Button type="link" size="small" onClick={() => setOpen(true)}>
            {TEXT.readMore}
          </Button>
        ) : null
      }
    >
      {latest ? (
        <Space direction="vertical" size={4} style={{ width: "100%" }}>
          <Typography.Text strong>{latest.title}</Typography.Text>
          <span className="aurora-muted">
            生成于 {formatDateTime(latest.created_at)} · 模型 {latest.model ?? "—"} · 引用{" "}
            {analysis?.citations.length ?? 0} 篇原文
          </span>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }} ellipsis={{ rows: 3 }}>
            {excerpt}
          </Typography.Paragraph>
        </Space>
      ) : (
        <EmptyHint text={TEXT.emptyReports} compact />
      )}
      <Drawer
        title={latest?.title ?? meta.dailyTitle}
        placement="right"
        width={760}
        open={open}
        onClose={() => setOpen(false)}
      >
        {detail.loading ? <span className="aurora-muted">加载中…</span> : null}
        {analysis ? (
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <span className="aurora-muted">
              统计区间 {formatDateTime(analysis.period_start)} ~ {formatDateTime(analysis.period_end)}
            </span>
            <MarkdownView content={analysis.content_md} />
            {analysis.citations.length ? (
              <Card size="small" title={`资料来源（${analysis.citations.length}）`} variant="outlined">
                <List
                  size="small"
                  dataSource={analysis.citations}
                  renderItem={(citation) => (
                    <List.Item>
                      <a href={citation.url} target="_blank" rel="noreferrer">
                        {citation.source_name ?? "来源"} · {citation.title}
                      </a>
                    </List.Item>
                  )}
                />
              </Card>
            ) : null}
          </Space>
        ) : null}
      </Drawer>
    </Card>
  );
}
