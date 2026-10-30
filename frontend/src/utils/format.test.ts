import { describe, expect, it } from "vitest";

import {
  compareToForecast,
  formatApiDetail,
  formatChangePct,
  formatDateTime,
  formatEventTime,
  healthLevel,
} from "./format";

describe("formatApiDetail", () => {
  it("keeps a plain string detail", () => {
    expect(formatApiDetail("未知地区", "Internal Server Error")).toBe("未知地区");
  });

  it("renders FastAPI validation issues with the field name", () => {
    const detail = [
      {
        type: "value_error",
        loc: ["body", "region"],
        msg: "Value error, 未知地区: zz",
        input: "zz",
      },
    ];
    expect(formatApiDetail(detail, "Unprocessable Entity")).toBe("region: 未知地区: zz");
  });

  it("joins multiple issues and falls back when there is nothing to show", () => {
    expect(
      formatApiDetail([{ loc: ["body", "name"], msg: "field required" }, { msg: "too long" }], "x"),
    ).toBe("name: field required；too long");
    expect(formatApiDetail(undefined, "Internal Server Error")).toBe("Internal Server Error");
  });

  it("falls back for an empty issue list", () => {
    expect(formatApiDetail([], "x")).toBe("x");
  });
});

describe("compareToForecast", () => {
  it("marks beat when value is above forecast", () => {
    expect(compareToForecast(0.5, 0.3)).toBe("beat");
  });

  it("marks miss when value is below forecast", () => {
    expect(compareToForecast(0.1, 0.3)).toBe("miss");
  });

  it("marks inline when equal or forecast missing", () => {
    expect(compareToForecast(0.3, 0.3)).toBe("inline");
    expect(compareToForecast(0.3, null)).toBe("inline");
    expect(compareToForecast(null, 0.3)).toBe("inline");
  });
});

describe("formatChangePct", () => {
  it("keeps sign and two decimals", () => {
    expect(formatChangePct(1.236)).toBe("+1.24%");
    expect(formatChangePct(-0.4)).toBe("-0.40%");
    expect(formatChangePct(null)).toBe("—");
  });
});

describe("healthLevel", () => {
  it("maps error counts to levels", () => {
    expect(healthLevel({ enabled: true, error_count: 0 })).toBe("ok");
    expect(healthLevel({ enabled: true, error_count: 2 })).toBe("warn");
    expect(healthLevel({ enabled: true, error_count: 3 })).toBe("bad");
    expect(healthLevel({ enabled: false, error_count: 0 })).toBe("off");
  });
});

describe("formatDateTime", () => {
  it("treats server timestamps as UTC and renders local minutes", () => {
    const date = new Date("2026-10-11T08:05:00Z");
    const pad = (value: number) => String(value).padStart(2, "0");
    const expected =
      `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
      `${pad(date.getHours())}:${pad(date.getMinutes())}`;

    expect(formatDateTime("2026-10-11T08:05:00")).toBe(expected);
    expect(formatDateTime(null)).toBe("—");
  });

  it("preserves timestamps that already include a timezone", () => {
    expect(formatDateTime("2026-10-11T08:05:00Z")).toBe(formatDateTime("2026-10-11T08:05:00"));
  });
});

describe("formatEventTime", () => {
  it("prefers the actual event time", () => {
    expect(formatEventTime("2026-10-30T13:40:00", "2026-10-30T14:00:00")).toEqual({
      text: formatDateTime("2026-10-30T13:40:00"),
      estimated: false,
    });
  });

  it("labels the fallback time instead of presenting it as event time", () => {
    expect(formatEventTime(null, "2026-10-30T14:00:00")).toEqual({
      text: `收录于 ${formatDateTime("2026-10-30T14:00:00")}`,
      estimated: true,
    });
  });

  it("never leaves time blank", () => {
    expect(formatEventTime(null, null)).toEqual({ text: "时间待核实", estimated: true });
  });
});
