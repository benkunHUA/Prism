import { Button, Card, List, Space, Tag } from "antd";

import { api } from "../../api/endpoints";
import type { GeoRegion } from "../../api/types";
import { CATEGORY_MAP } from "../../constants/categories";
import type { CategoryKey } from "../../constants/categories";
import { GEO_TEXT } from "../../constants/geo";
import type { GeoWindow } from "../../constants/geo";
import { MAP_BOARD_TEXT } from "../../constants/mapBoard";
import { useAsync } from "../../hooks/useAsync";
import { formatDateTime } from "../../utils/format";
import EmptyHint from "../EmptyHint";

interface Props {
  regions: GeoRegion[];
  windowKey: GeoWindow;
  selected: string | null;
  onSelect: (code: string | null) => void;
  loading?: boolean;
}

export default function RegionPanel({
  regions,
  windowKey,
  selected,
  onSelect,
  loading = false,
}: Props) {
  const detail = useAsync(
    () =>
      selected
        ? api.regionArticles(selected, { window: windowKey, limit: 30 })
        : Promise.resolve(null),
    [selected, windowKey],
  );

  if (!selected) {
    return (
      <Card size="small" variant="outlined" title={GEO_TEXT.rankingTitle} loading={loading}>
        {regions.length === 0 ? (
          <EmptyHint text={GEO_TEXT.empty} compact />
        ) : (
          <List
            size="small"
            dataSource={regions.slice(0, 12)}
            renderItem={(region, index) => (
              <List.Item style={{ cursor: "pointer" }} onClick={() => onSelect(region.code)}>
                <Space size={8} style={{ width: "100%" }}>
                  <Tag>{index + 1}</Tag>
                  <span style={{ flex: 1 }}>{region.name}</span>
                  <span className="aurora-muted">{region.count}</span>
                </Space>
              </List.Item>
            )}
          />
        )}
      </Card>
    );
  }

  const items = detail.data?.items ?? [];
  return (
    <Card
      size="small"
      variant="outlined"
      loading={detail.loading}
      title={GEO_TEXT.regionTitle(detail.data?.name ?? selected, windowKey)}
      extra={
        <Button type="link" size="small" onClick={() => onSelect(null)}>
          {GEO_TEXT.backToRanking}
        </Button>
      }
    >
      {items.length === 0 ? (
        <EmptyHint text={MAP_BOARD_TEXT.regionEmpty} compact />
      ) : (
        <List
          size="small"
          dataSource={items}
          renderItem={(item) => {
            const meta = CATEGORY_MAP[item.category as CategoryKey];
            return (
              <List.Item>
                <List.Item.Meta
                  title={
                    <a href={item.url} target="_blank" rel="noreferrer">
                      {item.title}
                    </a>
                  }
                  description={
                    <span className="aurora-muted">
                      <Tag color={meta?.color}>{meta?.label ?? item.category}</Tag>
                      {item.source_name ?? MAP_BOARD_TEXT.unknownSource} ·{" "}
                      {formatDateTime(item.published_at ?? item.fetched_at)}
                    </span>
                  }
                />
              </List.Item>
            );
          }}
        />
      )}
    </Card>
  );
}
