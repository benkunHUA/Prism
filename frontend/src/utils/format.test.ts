import { describe, expect, it } from "vitest";

import { compareToForecast, formatChangePct, formatDateTime, healthLevel } from "./format";

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
  it("renders ISO strings as local minutes", () => {
    expect(formatDateTime("2026-10-11T08:05:00")).toBe("2026-10-11 08:05");
    expect(formatDateTime(null)).toBe("—");
  });
});
