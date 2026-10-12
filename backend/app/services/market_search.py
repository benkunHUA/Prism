"""按关键词查东方财富 secid，并回验能否取到真实报价。

`MARKET_SYMBOLS` 里填的是 secid（形如 `100.SPX`），不用背市场号：先用
`search_assets` 按关键词搜出候选，再用 `fetch_quotes` 确认真的有报价。
命令行入口见 `scripts/find_secid.py`。
"""

from __future__ import annotations

import httpx

from app.services.marketdata import (
    EASTMONEY_HEADERS,
    FOLLOW_REDIRECTS,
    fetch_quotes,
)

SEARCH_URL = "https://searchapi.eastmoney.com/api/suggest/get"
DEFAULT_TIMEOUT = 20.0


def _client(timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout, headers=EASTMONEY_HEADERS)


def search_assets(keyword: str, *, client: httpx.Client | None = None,
                  count: int = 10, timeout: float = DEFAULT_TIMEOUT) -> list[dict]:
    """按关键词搜索标的，返回 [{secid, name, type_name, market}]（按相关度排序）。"""
    own = client is None
    client = client or _client(timeout)
    try:
        resp = client.get(
            SEARCH_URL,
            params={"input": keyword, "type": "14", "count": str(count)},
            headers=EASTMONEY_HEADERS,
            timeout=timeout,
            follow_redirects=FOLLOW_REDIRECTS,
        )
        resp.raise_for_status()
        rows = (resp.json().get("QuotationCodeTable") or {}).get("Data") or []
    finally:
        if own:
            client.close()
    return [
        {
            "secid": row.get("QuoteID", ""),
            "name": row.get("Name", ""),
            "type_name": row.get("SecurityTypeName", ""),
            "market": row.get("MktNum", ""),
        }
        for row in rows
        if row.get("QuoteID")
    ]


def resolve(keyword: str, *, client: httpx.Client | None = None,
            count: int = 10, timeout: float = DEFAULT_TIMEOUT) -> list[dict]:
    """搜索 + 回验：给候选补上 `quote` 字段，只有能取到报价的候选才带值。"""
    own = client is None
    client = client or _client(timeout)
    try:
        candidates = search_assets(keyword, client=client, count=count, timeout=timeout)
        quotes = fetch_quotes(client, [c["secid"] for c in candidates], timeout=timeout)
    finally:
        if own:
            client.close()
    for candidate in candidates:
        candidate["quote"] = quotes.get(candidate["secid"])
    return candidates


def to_spec(asset_class: str, name: str, secid: str) -> str:
    """拼成 `MARKET_SYMBOLS` 里的一项：`类别|名称=secid`。

    名称里的分隔符会被替换，避免在逗号分隔的配置里串项。
    """
    clean = name.replace(",", "，").replace("=", " ").replace("|", " ").strip()
    return f"{asset_class}|{clean}={secid}"
