import { Card, List, Tag, Typography } from "antd";

import { api } from "../api/endpoints";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime } from "../utils/format";

import EmptyHint from "./EmptyHint";

interface Props {
  category: string;
  limit?: number;
}

export default function ArticleList({ category, limit = 15 }: Props) {
  const { data, loading } = useAsync(() => api.articles(category, limit), [category, limit]);
  const items = data?.items ?? [];

  return (
    <Card size="small" title="最新原文材料" loading={loading} variant="outlined">
      {items.length === 0 ? (
        <EmptyHint text="该板块尚无采集到的原文" compact />
      ) : (
        <List
          size="small"
          dataSource={items}
          renderItem={(item) => (
            <List.Item>
              <List.Item.Meta
                title={
                  <a href={item.url} target="_blank" rel="noreferrer">
                    {item.title}
                  </a>
                }
                description={
                  <span className="aurora-muted">
                    {item.source_name ?? "未知来源"} · {formatDateTime(item.published_at ?? item.fetched_at)}
                  </span>
                }
              />
              {item.lang ? <Tag>{item.lang}</Tag> : null}
            </List.Item>
          )}
        />
      )}
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        展示最近 {limit} 条，完整列表可在后端 API 分页获取
      </Typography.Text>
    </Card>
  );
}
