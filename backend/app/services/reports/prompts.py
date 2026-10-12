from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.reports.context import build_board_context
from app.services.reports.specs import spec_for

CONTEXT_HEADER = "【板块结构化数据（来自本系统已确认条目，与材料冲突时以材料为准）】"


def _numbered_materials(articles, max_chars: int) -> str:
    lines = []
    for i, art in enumerate(articles, start=1):
        body = (art.summary or art.content_text or "")[:max_chars]
        lines.append(
            f"[{i}] 站点:{art.source.name if art.source else 'unknown'} | "
            f"时间:{art.fetched_at:%Y-%m-%d %H:%M} | 标题:{art.title}\n正文:{body}"
        )
    return "\n\n".join(lines)


def _context_part(db: Session, category: str) -> str:
    context = build_board_context(db, spec_for(category))
    return f"\n\n{CONTEXT_HEADER}\n{context}" if context else ""


def build_brief_prompt(db: Session, category: str, materials, settings: Settings) -> str:
    spec = spec_for(category)
    return (
        f"你是面向投资与研究的板块简报助手。基于以下 {len(materials)} 条材料（编号 [n] 对应材料），"
        f"用中文写「{spec.label}」板块快讯要点，3~5 条。{spec.brief_focus}\n"
        "每条格式：\n**事件：**一句话\n**影响：**对市场/政策/局势的提示\n**来源：**站点名称\n"
        "只能基于给定材料，禁止编造。"
        + _context_part(db, category)
        + "\n\n材料：\n"
        + _numbered_materials(materials, settings.max_analysis_input_chars)
    )


def build_daily_prompt(db: Session, category: str, materials, settings: Settings) -> str:
    spec = spec_for(category)
    sections = "\n".join(f"## {name}" for name in spec.daily_sections)
    return (
        f"你是严谨的宏观研究与投资参考分析师。基于以下 {len(materials)} 条编号材料"
        f"（[n] 站点 | 时间 | 标题 | 正文），为「{spec.label}」板块写一篇 1500~2500 字中文"
        f"《{spec.daily_title}》，Markdown 格式，固定章节：\n"
        f"{sections}\n## 资料来源\n"
        f"写作要求：{spec.daily_focus}\n"
        "规则：只能引用给定材料；资料来源逐行写 `- 编号 站点 · 标题`；"
        "禁止编造来源、数据与机构表态。"
        + _context_part(db, category)
        + "\n\n材料：\n"
        + _numbered_materials(materials, settings.max_analysis_input_chars)
    )
