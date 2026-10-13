export type ForecastVerdict = "beat" | "miss" | "inline";
export type HealthLevel = "ok" | "warn" | "bad" | "off";

export function compareToForecast(
  value: number | null | undefined,
  forecast: number | null | undefined,
): ForecastVerdict {
  if (value === null || value === undefined || forecast === null || forecast === undefined) {
    return "inline";
  }
  if (value > forecast) return "beat";
  if (value < forecast) return "miss";
  return "inline";
}

export function formatChangePct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function changeClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return "";
  return value >= 0 ? "up" : "down";
}

export function healthLevel(source: { enabled: boolean; error_count: number }): HealthLevel {
  if (!source.enabled) return "off";
  if (source.error_count === 0) return "ok";
  if (source.error_count < 3) return "warn";
  return "bad";
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 16);
}

export function formatNumber(value: number | null | undefined, unit = ""): string {
  if (value === null || value === undefined) return "—";
  return `${value}${unit}`;
}

export function todayLabel(iso: string | null | undefined): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

interface ValidationIssue {
  loc?: unknown[];
  msg?: string;
}

// FastAPI 校验失败时 detail 是数组，直接字符串化只会得到 "[object Object]"
export function formatApiDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail) return detail;
  if (!Array.isArray(detail)) return fallback;
  const parts = (detail as ValidationIssue[])
    .map((issue) => {
      if (!issue || typeof issue !== "object") return String(issue);
      const field = Array.isArray(issue.loc)
        ? issue.loc.filter((part) => part !== "body" && part !== "query").join(".")
        : "";
      const text = String(issue.msg ?? "").replace(/^Value error,\s*/, "");
      return field ? `${field}: ${text}` : text;
    })
    .filter(Boolean);
  return parts.length ? parts.join("；") : fallback;
}
