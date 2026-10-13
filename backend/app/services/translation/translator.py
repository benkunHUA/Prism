"""按批翻译文章标题与摘要并落库。"""

from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import Article
from app.services.llm import ChatProvider
from app.services.translation.prompts import build_translation_prompt

TITLE_LIMIT = 500
SUMMARY_INPUT_CHARS = 1000


def translate_articles(db: Session, articles: list[Article], provider: ChatProvider,
                       settings: Settings) -> tuple[int, list[str]]:
    """给还没有译文的文章补 `title_zh` / `summary_zh`，返回（成功篇数，错误列表）。

    不抛异常：单篇失败只进错误列表，交给回填命令重试。
    """
    pending = [article for article in articles if not article.title_zh]
    if not pending:
        return 0, []
    native = [article for article in pending if article.lang == "zh"]
    _write_native(db, native)
    todo = [article for article in pending if article.lang != "zh"]
    done = len(native)
    errors: list[str] = []
    size = max(1, settings.translate_batch_size)
    for start in range(0, len(todo), size):
        batch_done, batch_errors = _run_batch(
            db, todo[start:start + size], provider, settings
        )
        done += batch_done
        errors.extend(batch_errors)
    return done, errors


def _write_native(db: Session, articles: list[Article]) -> None:
    """原文已是中文，直接落原文，不调模型。"""
    if not articles:
        return
    for article in articles:
        article.title_zh = article.title
        article.summary_zh = article.summary or None
    db.commit()


def _run_batch(db: Session, batch: list[Article], provider: ChatProvider,
               settings: Settings) -> tuple[int, list[str]]:
    """翻一批；整批不可用时对半拆开重试，收敛到单篇。"""
    try:
        raw = provider.complete(
            [{"role": "user", "content": build_translation_prompt(_prompt_items(batch))}],
            temperature=0.0,
            max_tokens=settings.llm_translate_max_tokens,
        )
        parsed = _parse_array(raw)
    except Exception as exc:  # noqa: BLE001 - 整批失败一律降级重试
        if len(batch) == 1:
            return 0, [f"文章 {batch[0].id} 翻译失败: {exc}"]
        half = len(batch) // 2
        done = 0
        errors: list[str] = []
        for part in (batch[:half], batch[half:]):
            part_done, part_errors = _run_batch(db, part, provider, settings)
            done += part_done
            errors.extend(part_errors)
        return done, errors
    return _apply(db, batch, parsed)


def _prompt_items(batch: list[Article]) -> list[tuple[int, str, str]]:
    return [
        (index, article.title, (article.summary or "")[:SUMMARY_INPUT_CHARS])
        for index, article in enumerate(batch)
    ]


def _parse_array(raw: str) -> list:
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    payload = json.loads(text)
    if not isinstance(payload, list):
        raise ValueError("翻译结果不是 JSON 数组")
    return payload


def _apply(db: Session, batch: list[Article], parsed: list) -> tuple[int, list[str]]:
    """按 index 对号入座；重复、越界、缺标题的条目一律丢弃。"""
    hits: dict[int, tuple[str, str | None]] = {}
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        index = entry.get("index")
        title_zh = str(entry.get("title_zh") or "").strip()
        if not isinstance(index, int) or index in hits:
            continue
        if not 0 <= index < len(batch) or not title_zh:
            continue
        summary_zh = str(entry.get("summary_zh") or "").strip() or None
        hits[index] = (title_zh[:TITLE_LIMIT], summary_zh)

    done = 0
    errors: list[str] = []
    for index, article in enumerate(batch):
        hit = hits.get(index)
        if hit is None:
            errors.append(f"文章 {article.id} 翻译失败: 模型未返回该条")
            continue
        article.title_zh, article.summary_zh = hit
        done += 1
    db.commit()
    return done, errors
