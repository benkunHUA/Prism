import { Card, Tag } from "antd";

import type { SnapshotItem } from "../api/types";
import { TEXT } from "../constants/options";
import { changeClass, formatChangePct, formatDateTime } from "../utils/format";
import { summarizeOil } from "../utils/oil";

import EmptyHint from "./EmptyHint";
import StatCards from "./StatCards";

interface Props {
  items: SnapshotItem[];
  loading?: boolean;
}

export default function OilSnapshotCard({ items, loading = false }: Props) {
  const summary = summarizeOil(items);

  return (
    <Card
      size="small"
      title={TEXT.oilTitle}
      loading={loading}
      variant="outlined"
      extra={<Tag color="gold">{TEXT.oilUnit}</Tag>}
    >
      {summary.quotes.length === 0 ? (
        <EmptyHint text={TEXT.emptyOilSnapshots} compact />
      ) : (
        <StatCards
          items={[
            ...summary.quotes.map((quote) => ({
              label: quote.label,
              value: quote.price.toFixed(2),
              hint: (
                <span className={changeClass(quote.changePct)}>
                  本批次 {formatChangePct(quote.changePct)}
                  {quote.previousPrice === null ? "" : ` · 上轮 ${quote.previousPrice.toFixed(2)}`}
                </span>
              ),
            })),
            {
              label: TEXT.oilSpread,
              value: summary.spread === null ? "—" : summary.spread.toFixed(2),
              hint: TEXT.oilSpreadHint,
            },
            {
              label: TEXT.oilQuoteTime,
              value: formatDateTime(summary.capturedAt),
              hint: summary.batchId ? `批次 ${summary.batchId}` : undefined,
            },
          ]}
        />
      )}
    </Card>
  );
}
