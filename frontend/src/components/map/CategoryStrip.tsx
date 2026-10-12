import { Card, Space, Tooltip } from "antd";

import type { CategoryOverview } from "../../api/types";
import { CATEGORIES } from "../../constants/categories";
import { MAP_BOARD_STYLE, MAP_BOARD_TEXT } from "../../constants/mapBoard";
import CategoryChip from "./CategoryChip";

interface Props {
  overview: CategoryOverview[];
}

export default function CategoryStrip({ overview }: Props) {
  const byCategory = new Map(overview.map((item) => [item.category, item]));
  return (
    <Card
      size="small"
      variant="outlined"
      styles={{ body: { padding: MAP_BOARD_STYLE.stripPadding } }}
    >
      <Space size={20} wrap>
        {CATEGORIES.map((category) => {
          const item = byCategory.get(category.key);
          return (
            <Tooltip
              key={category.key}
              title={item?.latest_daily_title ?? MAP_BOARD_TEXT.stripPending(category.label)}
            >
              <CategoryChip
                category={category}
                shape="square"
                to={category.path}
                trailing={
                  <span className="aurora-muted">
                    {MAP_BOARD_TEXT.stripCount(item?.article_count ?? 0)}
                  </span>
                }
              />
            </Tooltip>
          );
        })}
      </Space>
    </Card>
  );
}
