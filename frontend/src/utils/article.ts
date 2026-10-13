import type { ArticleItem } from "../api/types";

/** 列表标题：有译文用译文，译文缺失或空白时回落原文。 */
export function displayTitle(item: Pick<ArticleItem, "title" | "title_zh">): string {
  const zh = item.title_zh?.trim();
  return zh || item.title;
}

/** 列表摘要：同上；两边都没有时返回空串，调用方据此不渲染整行。 */
export function displaySummary(
  item: Pick<ArticleItem, "summary" | "summary_zh">,
): string {
  const zh = item.summary_zh?.trim();
  return zh || (item.summary ?? "").trim();
}
