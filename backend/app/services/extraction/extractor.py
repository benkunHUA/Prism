from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import Article
from app.repositories import indicators as indicators_repo
from app.repositories import stances as stances_repo
from app.repositories import timeline as timeline_repo
from app.repositories import weapons as weapons_repo
from app.services.extraction.prompts import build_extraction_prompt
from app.services.extraction.risk import event_auto_verification
from app.services.extraction.schemas import (
    CATEGORY_MODEL,
    TimelineItemIn,
    WeaponItemIn,
)
from app.services.llm import ChatProvider
from app.services.urlutil import normalize_title


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _timeline_merge_key(category: str, item: TimelineItemIn) -> str:
    if item.group_key:
        raw = f"{category}|{item.group_key}"
    else:
        date = item.occurred_at.date().isoformat() if item.occurred_at else "no-date"
        raw = (
            f"{category}|{item.subtype}|{item.actor}|{item.region}|{date}|"
            f"{normalize_title(item.summary[:80])}"
        )
    return _sha(raw)


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    return json.loads(text)


def _write_timeline(db: Session, category: str, items: list[TimelineItemIn],
                    article_id: int | None, stats: dict) -> None:
    for item in items:
        verification = event_auto_verification(category, item.subtype, item.summary)
        _, created = timeline_repo.upsert_event(
            db, category=category, subtype=item.subtype, actor=item.actor,
            region=item.region, occurred_at=item.occurred_at, summary=item.summary,
            importance=item.importance, verification_status=verification,
            article_id=article_id, group_key=item.group_key,
            merge_key=_timeline_merge_key(category, item),
        )
        stats["created" if created else "updated"] += 1


def _write_weapons(db: Session, items: list[WeaponItemIn], article_id: int | None,
                   stats: dict) -> None:
    for item in items:
        merge_key = _sha(normalize_title(item.name) + "|" + normalize_title(item.origin))
        _, created = weapons_repo.upsert_weapon(
            db, name=item.name, original_name=item.original_name, origin=item.origin,
            weapon_type=item.weapon_type, params_text=item.params_text,
            lifecycle_status=item.lifecycle_status, merge_key=merge_key,
            verification_status="draft", article_id=article_id,
            first_seen_at=item.first_seen_at,
        )
        stats["created" if created else "updated"] += 1


def _article_categories(article: Article) -> list[str]:
    if article.source and article.source.source_categories:
        return [sc.category for sc in article.source.source_categories]
    return [article.category]


def extract_article(db: Session, article: Article, provider: ChatProvider,
                    settings: Settings) -> dict:
    """对单篇文章按所属板块提取并写库，返回统计。"""
    stats = {"created": 0, "updated": 0, "failed": 0}
    for category in _article_categories(article):
        model_cls = CATEGORY_MODEL.get(category)
        if model_cls is None:
            continue
        prompt = build_extraction_prompt(
            category, title=article.title, body=article.summary or article.content_text,
            url=article.url,
        )
        try:
            raw = provider.complete([{"role": "user", "content": prompt}],
                                    temperature=0.0, max_tokens=2500)
            payload = _parse_json(raw)
            parsed = model_cls.model_validate(payload)
        except Exception:  # noqa: BLE001
            stats["failed"] += 1
            continue
        if category == "politics":
            _write_timeline(db, "politics", parsed.events, article.id, stats)
            for stance in parsed.stances:
                stances_repo.create_stance(
                    db, topic=stance.topic, actor=stance.actor,
                    stance_text=stance.stance_text, tone=stance.tone,
                    stated_at=stance.stated_at, verification_status="draft",
                    article_id=article.id,
                )
                stats["created"] += 1
        elif category == "military":
            _write_timeline(db, "military", parsed.conflicts, article.id, stats)
            _write_weapons(db, parsed.weapons, article.id, stats)
        elif category == "economy":
            _write_timeline(db, "economy", parsed.policies, article.id, stats)
            for item in parsed.indicators:
                merge_key = _sha(normalize_title(item.indicator) + "|"
                                 + normalize_title(item.region) + "|" + item.period)
                _, created = indicators_repo.upsert_indicator(
                    db, indicator=item.indicator, region=item.region, period=item.period,
                    value=item.value, unit=item.unit, previous=item.previous,
                    forecast=item.forecast, released_at=item.released_at,
                    merge_key=merge_key, verification_status="confirmed",
                    article_id=article.id,
                )
                stats["created" if created else "updated"] += 1
        elif category == "finance":
            _write_timeline(db, "finance", parsed.events, article.id, stats)
    return stats
