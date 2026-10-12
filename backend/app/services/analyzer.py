from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import Analysis, Category
from app.repositories import analyses as analyses_repo
from app.repositories import articles as articles_repo
from app.services.llm import ChatProvider
from app.services.reports import build_brief_prompt, build_daily_prompt, spec_for

ALL = [c.value for c in Category]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
    prompt = build_brief_prompt(db, category, materials, settings)
    content = provider.complete(
        [{"role": "user", "content": prompt}], temperature=0.2, max_tokens=2000
    )
    spec = spec_for(category)
    return analyses_repo.create_analysis(
        db, kind="brief", category=category,
        title=f"{spec.label}快讯 {until:%H:%M}",
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
    prompt = build_daily_prompt(db, category, materials, settings)
    content = provider.complete(
        [{"role": "user", "content": prompt}], temperature=0.2, max_tokens=4000
    )
    spec = spec_for(category)
    analysis = analyses_repo.create_analysis(
        db, kind="daily", category=category,
        title=f"{spec.daily_title} · {until:%Y-%m-%d}",
        content_md=content, period_start=since, period_end=until,
        model=settings.llm_model,
    )
    ids = _parse_citation_ids(content, len(materials))
    valid_ids = [materials[i - 1].id for i in ids if i <= len(materials)]
    if valid_ids:
        analyses_repo.link_articles(db, analysis, valid_ids)
    return analysis
