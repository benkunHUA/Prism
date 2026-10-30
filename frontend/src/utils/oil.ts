import type { SnapshotItem } from "../api/types";
import { OIL_ASSETS } from "../constants/options";

export interface OilQuote {
  code: string;
  label: string;
  price: number;
  changePct: number | null;
  previousPrice: number | null;
  capturedAt: string;
  batchId: string | null;
  stale: boolean;
}

export interface OilSummary {
  quotes: OilQuote[];
  spread: number | null;
  batchId: string | null;
  capturedAt: string | null;
  hasStaleQuote: boolean;
}

export function summarizeOil(items: SnapshotItem[]): OilSummary {
  const batchIds: string[] = [];
  for (const item of items) {
    if (item.batch_id && !batchIds.includes(item.batch_id)) batchIds.push(item.batch_id);
    if (batchIds.length >= 2) break;
  }
  const latestBatch = batchIds[0];
  const previousBatch = batchIds[1];
  const latest = new Map<string, SnapshotItem>();
  const previous = new Map<string, SnapshotItem>();
  for (const item of items) {
    if (item.batch_id === latestBatch && item.price !== null && item.price > 0) {
      latest.set(item.asset_code, item);
    } else if (item.batch_id === previousBatch && item.price !== null && item.price > 0) {
      previous.set(item.asset_code, item);
    }
  }

  const quotes = OIL_ASSETS.flatMap((asset) => {
    const latestItem = latest.get(asset.code);
    const item = latestItem ?? previous.get(asset.code);
    if (!item || item.price === null) return [];
    return [
      {
        code: asset.code,
        label: asset.label,
        price: item.price,
        changePct: item.change_pct,
        previousPrice: latestItem ? previous.get(asset.code)?.price ?? null : null,
        capturedAt: item.captured_at,
        batchId: item.batch_id,
        stale: !latestItem,
      },
    ];
  });
  const wti = quotes.find((quote) => quote.code === "102.CL00Y");
  const brent = quotes.find((quote) => quote.code === "112.B00Y");
  return {
    quotes,
    spread: wti && brent ? wti.price - brent.price : null,
    batchId: latestBatch ?? null,
    capturedAt: quotes[0]?.capturedAt ?? null,
    hasStaleQuote: quotes.some((quote) => quote.stale),
  };
}
