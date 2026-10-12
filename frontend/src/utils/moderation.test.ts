import { describe, expect, it } from "vitest";

import type { ModerationItem } from "../api/types";
import { countByType, draftFrom, editPayload, moderationTitle } from "./moderation";

const weapon: ModerationItem = {
  type: "weapon",
  id: 3,
  name: "PrSM",
  origin: "美国",
  lifecycle_status: "测试",
  params_text: "射程 499 公里",
};

describe("moderationTitle", () => {
  it("labels weapons by name", () => {
    expect(moderationTitle(weapon)).toBe("PrSM");
  });

  it("labels timeline items by category and subtype", () => {
    expect(moderationTitle({ type: "timeline", id: 1, category: "military", subtype: "冲突进展" })).toBe(
      "military · 冲突进展",
    );
  });
});

describe("draftFrom / editPayload", () => {
  it("round-trips weapon fields", () => {
    const payload = editPayload(weapon, draftFrom(weapon));
    expect(payload).toEqual({
      action: "edit",
      params_text: "射程 499 公里",
      lifecycle_status: "测试",
    });
  });

  it("parses indicator value as number", () => {
    const indicator: ModerationItem = { type: "indicator", id: 9, value: 0.4 };
    expect(editPayload(indicator, { ...draftFrom(indicator), value: "0.7" })).toEqual({
      action: "edit",
      value: 0.7,
    });
  });
});

describe("countByType", () => {
  it("counts each moderation type", () => {
    expect(
      countByType([weapon, { type: "stance", id: 2 }, { type: "stance", id: 5 }]),
    ).toEqual({ weapon: 1, stance: 2 });
  });
});
