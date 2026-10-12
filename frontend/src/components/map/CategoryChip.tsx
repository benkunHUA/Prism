import type { CSSProperties, ReactNode } from "react";
import { Link } from "react-router-dom";

import type { CategoryMeta } from "../../constants/categories";
import {
  CHIP_CIRCLE_RADIUS,
  CHIP_DIMMED_OPACITY,
  CHIP_MARK_STYLE,
  CHIP_SQUARE_RADIUS,
  CHIP_STYLE,
} from "../../constants/mapBoard";

interface Props {
  category: CategoryMeta;
  shape?: "circle" | "square";
  dimmed?: boolean;
  to?: string;
  onClick?: () => void;
  trailing?: ReactNode;
}

/** 板块色块 + 名称的行内 chip，被图例与板块条共用。 */
export default function CategoryChip({
  category,
  shape = "circle",
  dimmed = false,
  to,
  onClick,
  trailing,
}: Props) {
  const style: CSSProperties = {
    ...CHIP_STYLE,
    opacity: dimmed ? CHIP_DIMMED_OPACITY : 1,
    cursor: onClick ? "pointer" : undefined,
  };
  const content = (
    <>
      <i
        style={{
          ...CHIP_MARK_STYLE,
          borderRadius: shape === "circle" ? CHIP_CIRCLE_RADIUS : CHIP_SQUARE_RADIUS,
          background: category.color,
        }}
      />
      {category.label}
      {trailing}
    </>
  );
  if (to) {
    return (
      <Link to={to} style={style}>
        {content}
      </Link>
    );
  }
  return (
    <span onClick={onClick} style={style}>
      {content}
    </span>
  );
}
