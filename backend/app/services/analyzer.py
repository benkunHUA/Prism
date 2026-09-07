from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import Analysis, Category
from app.repositories import analyses as analyses_repo
from app.repositories import articles as articles_repo
from app.services.llm import ChatProvider

CATEGORY_LABELS = {
    Category.politics.value: "政治",
    Category.economy.value: "经济",
    Category.finance.value: "金融",
    Category.military.value: "军事",
}
ALL = [c.value for c in Category]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _numbered_materials(articles, settings: Settings) -> str:
    lines = []
    for i, art in enumerate(articles, start=1):
        body = (art.summary or art.content_text or "")[: settings.max_analysis_input_chars]
        lines.append(
            f"[{i}] 站点:{art.source.name if art.source else 'unknown'} | 时间:{art.fetched_at:%Y-%m-%d %H:%M} | "
            f"标题:{art.title}\n正文:{body}"
        )
    return "\n\n".join(lines)


def _parse_citation_ids(content_md: str, max_id: int) -> list[int]:
    section = content_md.rsplit("资料来源", 1)[-1]
    ids = []
    for line in section.splitlines():
        m = re.match(r"^\s*[-*]?\s*(\d+)[.、)）]?\s*", line)
        if not m:
            continue
        n = int(m.group(1))
        if 1 <= n <= max_id and n not in ids:
            ids.append(n)
    return ids


def generate_brief(db: Session, category: str, provider: ChatProvider,
                   settings: Settings, *, since: datetime | None = None) -> Analysis | None:
    until = _now()
    since = since or (until - timedelta(hours=6))
    materials = articles_repo.articles_for_analysis(
        db, category, since, until, limit=settings.top_articles_per_analysis
    )
    if not materials:
        return None
    prompt = (
        f"你是面向投资与研究的板块简报助手。基于以下 {len(materials)} 条材料（编号 [n] 对应材料），"
        f"用中文写 {category} 板块快讯要点，3~5 条。每条格式：\n"
        "**事件：**一句话\n**影响：**对市场/政策/局势的提示\n**来源：**站点名称\n"
        "只能基于给定材料，禁止编造。\n\n材料：\n" + _numbered_materials(materials, settings)
    )
    content = provider.complete(
        [{"role": "user", "content": prompt}], temperature=0.2, max_tokens=2000
    )
    return analyses_repo.create_analysis(
        db, kind="brief", category=category,
        title=f"{CATEGORY_LABELS.get(category, category)}快讯 {until:%H:%M}",
        content_md=content, period_start=since, period_end=until,
        model=settings.llm_model,
    )


def generate_daily(db: Session, category: str, provider: ChatProvider,
                   settings: Settings, *, until: datetime | None = None) -> Analysis | None:
    until = until or _now()
    since = until - timedelta(hours=24)
    materials = articles_repo.articles_for_analysis(
        db, category, since, until, limit=settings.top_articles_per_analysis
    )
    if not materials:
        return None
    prompt = (
        f"你是严谨的宏观研究与投资参考分析师。基于以下 {len(materials)} 条编号材料"
        f"（[n] 站点 | 时间 | 标题 | 正文），为「{CATEGORY_LABELS.get(category, category)}」板块"
        "写一篇 1500~2500 字中文分析，Markdown 格式，固定章节：\n"
        "## 要点速览\n## 重大事件与事实\n## 影响与传导分析\n## 风险与关注信号\n## 资料来源\n"
        "规则：只能引用给定材料；资料来源逐行写 `- 编号 站点 · 标题`；"
        "禁止编造来源、数据与机构表态。\n\n材料：\n" + _numbered_materials(materials, settings)
    )
    content = provider.complete(
        [{"role": "user", "content": prompt}], temperature=0.2, max_tokens=4000
    )
    analysis = analyses_repo.create_analysis(
        db, kind="daily", category=category,
        title=f"{CATEGORY_LABELS.get(category, category)}每日分析 {until:%Y-%m-%d}",
        content_md=content, period_start=since, period_end=until,
        model=settings.llm_model,
    )
    ids = _parse_citation_ids(content, len(materials))
    valid_ids = [materials[i - 1].id for i in ids if i <= len(materials)]
    if valid_ids:
        analyses_repo.link_articles(db, analysis, valid_ids)
    return analysis
