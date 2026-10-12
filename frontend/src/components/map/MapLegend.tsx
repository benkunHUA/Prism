import { Segmented, Space, Tooltip } from "antd";

import { CATEGORIES } from "../../constants/categories";
import { GEO_TEXT, GEO_WINDOWS } from "../../constants/geo";
import type { GeoWindow } from "../../constants/geo";
import CategoryChip from "./CategoryChip";

interface Props {
  windowKey: GeoWindow;
  onWindowChange: (value: GeoWindow) => void;
  activeCategories: string[];
  onToggleCategory: (key: string) => void;
  untagged: number;
}

export default function MapLegend({
  windowKey,
  onWindowChange,
  activeCategories,
  onToggleCategory,
  untagged,
}: Props) {
  return (
    <Space size={12} wrap style={{ width: "100%", justifyContent: "space-between" }}>
      <Space size={14} wrap>
        {CATEGORIES.map((category) => (
          <Tooltip key={category.key} title={GEO_TEXT.legendHint}>
            <CategoryChip
              category={category}
              dimmed={!activeCategories.includes(category.key)}
              onClick={() => onToggleCategory(category.key)}
            />
          </Tooltip>
        ))}
        {untagged > 0 ? <span className="aurora-muted">{GEO_TEXT.untagged(untagged)}</span> : null}
      </Space>
      <Segmented
        value={windowKey}
        options={GEO_WINDOWS}
        onChange={(value) => onWindowChange(value as GeoWindow)}
      />
    </Space>
  );
}
