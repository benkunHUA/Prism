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
                  {quote.stale ? "上轮快照" : "本批次"} {formatChangePct(quote.changePct)}
                  {quote.stale
                    ? ` · ${formatDateTime(quote.capturedAt)}`
                    : quote.previousPrice === null
                      ? ""
                      : ` · 上轮 ${quote.previousPrice.toFixed(2)}`}
                </span>
              ),
            })),
            {
              label: TEXT.oilSpread,
              value: summary.spread === null ? "—" : summary.spread.toFixed(2),
              hint: summary.hasStaleQuote ? `${TEXT.oilSpreadHint}（含上轮）` : TEXT.oilSpreadHint,
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
