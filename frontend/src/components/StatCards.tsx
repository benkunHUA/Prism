import { Card, Col, Row, Typography } from "antd";
import type { ReactNode } from "react";

export interface StatItem {
  label: string;
  value: ReactNode;
  hint?: string;
}

interface Props {
  items: StatItem[];
}

export default function StatCards({ items }: Props) {
  return (
    <Row gutter={12}>
      {items.map((item) => (
        <Col xs={24} sm={12} md={6} key={item.label}>
          <Card size="small" variant="outlined">
            <span className="aurora-muted">{item.label}</span>
            <Typography.Title level={4} style={{ margin: "4px 0 0" }}>
              {item.value}
            </Typography.Title>
            {item.hint ? <span className="aurora-muted">{item.hint}</span> : null}
          </Card>
        </Col>
      ))}
    </Row>
  );
}
