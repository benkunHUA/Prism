import { Empty } from "antd";

interface Props {
  text: string;
  compact?: boolean;
}

export default function EmptyHint({ text, compact = false }: Props) {
  return (
    <Empty
      image={Empty.PRESENTED_IMAGE_SIMPLE}
      description={<span className="aurora-muted">{text}</span>}
      style={compact ? { margin: "8px 0" } : { margin: "24px 0" }}
    />
  );
}
