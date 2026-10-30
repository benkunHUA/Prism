import { describe, expect, it } from "vitest";

import type { SnapshotItem } from "../api/types";
import { summarizeOil } from "./oil";

function snapshot(
  asset_code: string,
  price: number | null,
  batch_id: string,
  change_pct: number | null = 0,
): SnapshotItem {
  return {
    id: Number(`${asset_code.length}${batch_id.length}`),
    asset_code,
    asset_name: asset_code,
    asset_class: "commodity",
    price,
    change_pct,
    captured_at: batch_id === "b2" ? "2026-10-30T14:00:00" : "2026-10-30T10:00:00",
    batch_id,
    source: "eastmoney",
  };
}

describe("summarizeOil", () => {
  it("returns WTI, Brent and the current spread from the latest batch", () => {
    const result = summarizeOil([
      snapshot("102.CL00Y", 102.75, "b2", 0.74),
      snapshot("112.B00Y", 110.4, "b2", -1.15),
      snapshot("102.CL00Y", 101.58, "b1", -1.64),
      snapshot("112.B00Y", 111.7, "b1", 0.2),
    ]);

    expect(result.quotes.map((quote) => quote.label)).toEqual(["WTI 原油", "布伦特原油"]);
    expect(result.quotes[0]).toMatchObject({ price: 102.75, previousPrice: 101.58 });
    expect(result.spread).toBeCloseTo(-7.65);
  });

  it("ignores zero prices returned during market close", () => {
    const result = summarizeOil([
      snapshot("102.CL00Y", 102.75, "b2"),
      snapshot("112.B00Y", 0, "b2"),
    ]);

    expect(result.quotes.map((quote) => quote.code)).toEqual(["102.CL00Y"]);
    expect(result.spread).toBeNull();
  });

  it("falls back to the previous valid quote and marks it stale", () => {
    const result = summarizeOil([
      snapshot("102.CL00Y", 102.75, "b2"),
      snapshot("112.B00Y", 0, "b2"),
      snapshot("112.B00Y", 110.4, "b1"),
    ]);

    expect(result.quotes.find((quote) => quote.code === "112.B00Y")).toMatchObject({
      price: 110.4,
      stale: true,
    });
    expect(result.spread).toBeCloseTo(-7.65);
    expect(result.hasStaleQuote).toBe(true);
  });
});
