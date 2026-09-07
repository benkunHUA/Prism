from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from types import SimpleNamespace

import feedparser
import httpx
import trafilatura
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories import articles as articles_repo
from app.repositories import sources as sources_repo
from app.services.urlutil import dedupe_hash, normalize_url

USER_AGENT = "AuroraBot/0.1 (+personal research tool; polite fetcher)"


def _clean_html(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)


def _get_with_retry(client: httpx.Client, url: str, timeout: float, tries: int = 3) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(tries):
        try:
            resp = client.get(url, timeout=timeout, follow_redirects=True)
            resp.raise_for_status()
            return resp
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < tries - 1:
                time.sleep(2**attempt)
    if last_error:
        raise last_error
    raise RuntimeError("unreachable")


def _first_category(source) -> str:
    cats = getattr(source, "categories", None)
    if cats is None:
        cats = [sc.category for sc in getattr(source, "source_categories", [])]
    return cats[0] if cats else "politics"


def _fetch_full_text(client: httpx.Client, url: str, timeout: float) -> tuple[str, str]:
    """返回 (标题, 正文)。失败时正文为空，不抛错。"""
    try:
        resp = client.get(url, timeout=timeout, follow_redirects=True)
        text = trafilatura.extract(resp.text) or ""
        meta = trafilatura.extract_metadata(resp.text)
        title = (meta.title if meta and meta.title else "").strip()
        return title, text
    except httpx.HTTPError:
        return "", ""


def fetch_source(source, settings: Settings, client: httpx.Client) -> tuple[list[dict], str | None]:
    """抓单个源（source 为轻量快照对象），返回 (待入库条目, 错误消息)。"""
    try:
        resp = _get_with_retry(client, source.url, settings.request_timeout_s)
        items: list[dict] = []
        primary = _first_category(source)
        if source.feed_type == "rss":
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[: settings.max_articles_per_source]:
                url = normalize_url(entry.get("link", ""))
                title = (entry.get("title") or "").strip()
                if not url or not title:
                    continue
                summary = _clean_html(entry.get("summary", ""))
                content_text = summary
                if len(content_text) < 200:
                    _, content_text = _fetch_full_text(
                        client, url, min(15.0, settings.request_timeout_s)
                    )
                content_text = content_text[: settings.max_content_chars]
                published = None
                if entry.get("published_parsed"):
                    t = entry["published_parsed"]
                    published = datetime(t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)
                items.append(
                    {
                        "source_id": source.id,
                        "category": primary,
                        "url": url,
                        "title": title,
                        "summary": summary[:2000],
                        "content_text": content_text,
                        "published_at": published,
                        "lang": source.lang,
                        "dedupe_hash": dedupe_hash(url, title),
                    }
                )
        else:
            content_text = trafilatura.extract(resp.text) or ""
            meta = trafilatura.extract_metadata(resp.text)
            title = (meta.title if meta and meta.title else source.name).strip()
            items.append(
                {
                    "source_id": source.id,
                    "category": primary,
                    "url": normalize_url(source.url),
                    "title": title,
                    "summary": content_text[:2000],
                    "content_text": content_text[: settings.max_content_chars],
                    "published_at": None,
                    "lang": source.lang,
                    "dedupe_hash": dedupe_hash(source.url, title),
                }
            )
        return items, None
    except httpx.HTTPError as exc:
        return [], f"{type(exc).__name__}: {exc}"


def collect_new(db: Session, *, category: str | None = None,
                client: httpx.Client | None = None,
                settings: Settings | None = None) -> dict:
    settings = settings or Settings(_env_file=None)
    own_client = client is None
    client = client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=settings.request_timeout_s)
    try:
        sources = [
            s for s in sources_repo.list_sources(db)
            if s.enabled and (category is None or any(sc.category == category for sc in s.source_categories))
        ]
        # 主线程内做快照，避免跨线程访问 Session 对象
        snapshots = [
            SimpleNamespace(
                id=s.id, name=s.name, url=s.url, feed_type=s.feed_type, lang=s.lang,
                categories=[sc.category for sc in s.source_categories],
            )
            for s in sources
        ]
        results: dict[int, tuple[list[dict], str | None]] = {}
        with ThreadPoolExecutor(max_workers=settings.collect_concurrency) as pool:
            futures = {pool.submit(fetch_source, snap, settings, client): snap for snap in snapshots}
            for fut in as_completed(futures):
                snap = futures[fut]
                results[snap.id] = fut.result()
        fetched = new = 0
        errors: list[str] = []
        source_by_id = {s.id: s for s in sources}
        for snap in snapshots:
            source = source_by_id[snap.id]
            items, error = results.get(snap.id, ([], "source not fetched"))
            if error:
                errors.append(f"{source.name}: {error}")
                sources_repo.set_source_health(db, source, ok=False, error=error)
                continue
            fetched += len(items)
            new += articles_repo.insert_articles(db, items)
            sources_repo.set_source_health(db, source, ok=True)
        return {"fetched": fetched, "new": new, "errors": errors}
    finally:
        if own_client:
            client.close()
