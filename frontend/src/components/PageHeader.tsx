import { Space, Typography } from "antd";
import type { ReactNode } from "react";

interface Props {
  title: string;
  tagline?: string;
  extra?: ReactNode;
}

export default function PageHeader({ title, tagline, extra }: Props) {
  return (
    <Space
      style={{ width: "100%", justifyContent: "space-between", alignItems: "flex-end" }}
      align="end"
    >
      <div>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {title}
        </Typography.Title>
        {tagline ? <span className="aurora-muted">{tagline}</span> : null}
      </div>
      {extra}
    </Space>
  );
}
