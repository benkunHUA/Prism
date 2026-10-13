import { describe, expect, it } from "vitest";

import { displaySummary, displayTitle } from "./article";

describe("displayTitle", () => {
  it("prefers the translation", () => {
    expect(displayTitle({ title: "Fed hikes rates", title_zh: "美联储加息" })).toBe("美联储加息");
  });

  it("falls back to the original when missing or blank", () => {
    expect(displayTitle({ title: "Fed hikes rates", title_zh: null })).toBe("Fed hikes rates");
    expect(displayTitle({ title: "Fed hikes rates", title_zh: "   " })).toBe("Fed hikes rates");
  });
});

describe("displaySummary", () => {
  it("prefers the translation", () => {
    expect(displaySummary({ summary: "original", summary_zh: "中文要点" })).toBe("中文要点");
  });

  it("falls back to the original, then to an empty string", () => {
    expect(displaySummary({ summary: "original", summary_zh: null })).toBe("original");
    expect(displaySummary({ summary: null, summary_zh: null })).toBe("");
  });
});
