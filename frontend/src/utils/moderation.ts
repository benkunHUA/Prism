import type { ModerationItem, ModerationPatch } from "../api/types";

export interface FieldSpec {
  label: string;
  value: string;
}

export function moderationTitle(item: ModerationItem): string {
  switch (item.type) {
    case "timeline":
      return item.category ? `${item.category} · ${item.subtype ?? "事件"}` : (item.subtype ?? "事件");
    case "weapon":
      return item.name ?? "武器";
    case "stance":
      return `${item.topic ?? "议题"} · ${item.actor ?? "主体"}`;
    case "indicator":
      return `${item.region ?? "—"} ${item.period ?? "—"} ${item.indicator ?? "指标"}`;
    default:
      return "待确认条目";
  }
}

export function moderationFields(item: ModerationItem): FieldSpec[] {
  switch (item.type) {
    case "timeline":
      return [
        { label: "摘要", value: item.summary ?? "—" },
        { label: "重要性", value: item.importance ?? "—" },
      ];
    case "weapon":
      return [
        { label: "国别 / 类型", value: `${item.origin ?? "—"} / ${item.lifecycle_status ?? "—"}` },
        { label: "参数", value: item.params_text ?? "—" },
      ];
    case "stance":
      return [
        { label: "基调", value: item.tone ?? "—" },
        { label: "表态", value: item.stance_text ?? "—" },
      ];
    case "indicator":
      return [{ label: "数值", value: item.value === null || item.value === undefined ? "—" : String(item.value) }];
    default:
      return [];
  }
}

export interface ModerationEditDraft {
  summary: string;
  importance: string;
  params_text: string;
  lifecycle_status: string;
  stance_text: string;
  tone: string;
  value: string;
}

export function draftFrom(item: ModerationItem): ModerationEditDraft {
  return {
    summary: item.summary ?? "",
    importance: item.importance ?? "medium",
    params_text: item.params_text ?? "",
    lifecycle_status: item.lifecycle_status ?? "研发",
    stance_text: item.stance_text ?? "",
    tone: item.tone ?? "中性",
    value: item.value === null || item.value === undefined ? "" : String(item.value),
  };
}

export function editPayload(item: ModerationItem, draft: ModerationEditDraft): ModerationPatch {
  const base: ModerationPatch = { action: "edit" };
  if (item.type === "timeline") {
    return { ...base, summary: draft.summary, importance: draft.importance };
  }
  if (item.type === "weapon") {
    return { ...base, params_text: draft.params_text, lifecycle_status: draft.lifecycle_status };
  }
  if (item.type === "stance") {
    return { ...base, stance_text: draft.stance_text, tone: draft.tone };
  }
  const parsed = Number(draft.value);
  return { ...base, value: Number.isFinite(parsed) ? parsed : 0 };
}

export function countByType(items: ModerationItem[]): Record<string, number> {
  return items.reduce<Record<string, number>>((acc, item) => {
    acc[item.type] = (acc[item.type] ?? 0) + 1;
    return acc;
  }, {});
}
