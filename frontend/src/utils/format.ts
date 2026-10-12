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
