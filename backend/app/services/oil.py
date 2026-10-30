from __future__ import annotations

import re

from app.models.entities import Article

_EN_OIL_TERMS = re.compile(
    r"\b(?:oil|crude|brent|wti|opec|petroleum|refin\w*|gasoline|diesel|barrels?)\b",
    re.IGNORECASE,
)
_ZH_OIL_TERMS = (
    "原油",
    "石油",
    "布伦特",
    "欧佩克",
    "炼油",
    "成品油",
    "汽油",
    "柴油",
    "减产",
    "增产",
)


def is_oil_related(article: Article) -> bool:
    """标题、摘要或正文命中原油主题即视为相关。"""
    source_name = article.source.name if article.source else ""
    text = " ".join(
        part for part in (article.title, article.summary, article.content_text, source_name) if part
    )
    return bool(_EN_OIL_TERMS.search(text) or any(term in text for term in _ZH_OIL_TERMS))


def prioritize_oil_materials(materials: list[Article], limit: int) -> list[Article]:
    """金融分析选材时给原油文章保留约三分之一名额，避免被泛金融新闻淹没。"""
    if limit <= 0 or not materials:
        return []
    oil = [article for article in materials if is_oil_related(article)]
    if not oil:
        return materials[:limit]

    selected = oil[: min(limit, len(oil), max(3, limit // 3))]
    selected_ids = {article.id for article in selected}
    for article in materials:
        if len(selected) >= limit:
            break
        if article.id not in selected_ids:
            selected.append(article)
            selected_ids.add(article.id)
    return sorted(selected, key=lambda article: article.fetched_at, reverse=True)
