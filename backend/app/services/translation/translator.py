"""按批翻译文章标题与摘要并落库。"""

from __future__ import annotations

import json
import re
from contextlib import suppress

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import Article
from app.services.llm import ChatProvider
from app.services.translation.prompts import build_translation_prompt

TITLE_LIMIT = 500
SUMMARY_INPUT_CHARS = 1000
FAILURE_TEMPLATE = "文章 {article_id} 翻译失败: {reason}"


def _fail(article: Article, reason: object) -> str:
    return FAILURE_TEMPLATE.format(article_id=article.id, reason=reason)


def translate_articles(db: Session, articles: list[Article], provider: ChatProvider,
                       settings: Settings) -> tuple[int, list[str]]:
    """给还没有译文的文章补 `title_zh` / `summary_zh`，返回（成功篇数，错误列表）。

    不抛异常：单篇失败只进错误列表，交给回填命令重试。
    """
    pending = [article for article in articles if not article.title_zh]
    if not pending:
        return 0, []
    native = [article for article in pending if article.lang == "zh" and article.title]
    blank = [article for article in pending if article.lang == "zh" and not article.title]
    todo = [article for article in pending if article.lang != "zh"]

    done, errors = _write_native(db, native)
    errors.extend(_fail(article, "原文标题为空") for article in blank)

    size = max(1, settings.translate_batch_size)
    for start in range(0, len(todo), size):
        batch_done, batch_errors = _run_batch(db, todo[start:start + size], provider, settings)
        done += batch_done
        errors.extend(batch_errors)
    return done, errors


def _write_native(db: Session, articles: list[Article]) -> tuple[int, list[str]]:
    """原文已是中文，直接落原文，不调模型。"""
    if not articles:
        return 0, []
    for article in articles:
        article.title_zh = article.title[:TITLE_LIMIT]
        article.summary_zh = article.summary or None
    written, errors = _commit(db, articles)
    return (len(articles) if written else 0), errors


def _commit(db: Session, articles: list[Article]) -> tuple[bool, list[str]]:
    """提交；落库失败时回滚并把整批计入错误，绝不让异常逃逸。"""
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001 - 落库失败只降级为错误，不中断整轮
        _rollback(db)
        return False, [_fail(article, exc) for article in articles]
    return True, []


def _rollback(db: Session) -> None:
    """连接已断时 rollback 自身也会抛，这里只求不扩散。"""
    with suppress(Exception):
        db.rollback()


def _run_batch(db: Session, batch: list[Article], provider: ChatProvider,
               settings: Settings) -> tuple[int, list[str]]:
    """翻一批；模型侧整批不可用时对半拆开重试，收敛到单篇。"""
    try:
        raw = provider.complete(
            [{"role": "user", "content": build_translation_prompt(_prompt_items(batch))}],
            temperature=0.0,
            max_tokens=settings.llm_translate_max_tokens,
        )
        parsed = _parse_array(raw)
    except Exception as exc:  # noqa: BLE001 - 整批失败一律降级重试
        if len(batch) == 1:
            return 0, [_fail(batch[0], exc)]
        half = len(batch) // 2
        done = 0
        errors: list[str] = []
        for part in (batch[:half], batch[half:]):
            part_done, part_errors = _run_batch(db, part, provider, settings)
            done += part_done
            errors.extend(part_errors)
        return done, errors
    try:
        return _apply(db, batch, parsed)
    except Exception as exc:  # noqa: BLE001 - 写库异常同样不能逃逸
        _rollback(db)
        return 0, [_fail(article, exc) for article in batch]


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
    """按 index 对号入座；非整数 index、重复、越界、缺标题的条目一律丢弃。"""
    hits: dict[int, tuple[str, str | None]] = {}
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        index = entry.get("index")
        title_zh = entry.get("title_zh")
        if isinstance(index, bool) or not isinstance(index, int) or index in hits:
            continue
        if not 0 <= index < len(batch) or not isinstance(title_zh, str):
            continue
        title_zh = title_zh.strip()
        if not title_zh:
            continue
        raw_summary = entry.get("summary_zh")
        summary_zh = raw_summary.strip() if isinstance(raw_summary, str) else ""
        hits[index] = (title_zh[:TITLE_LIMIT], summary_zh or None)

    done = 0
    errors: list[str] = []
    for index, article in enumerate(batch):
        hit = hits.get(index)
        if hit is None:
            errors.append(_fail(article, "模型未返回该条"))
            continue
        article.title_zh, article.summary_zh = hit
        done += 1
    if not hits:
        return 0, errors
    written, commit_errors = _commit(db, batch)
    return (done if written else 0), errors + commit_errors
