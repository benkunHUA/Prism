from __future__ import annotations

import csv
import io
import uuid

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories import snapshots as snapshots_repo

STOOQ_URL = "https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
EASTMONEY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Referer": "https://quote.eastmoney.com/",
}


def _parse_spec(spec: str) -> tuple[str, str, str]:
    """解析 "index|标普500=100.SPX" → (asset_class, name, code)。"""
    head, _, code = spec.partition("=")
    code = code.strip()
    if "|" in head:
        asset_class, name = head.split("|", 1)
    else:
        asset_class, name = "index", head
    return asset_class.strip(), name.strip(), code


class EastmoneyProvider:
    """东方财富批量行情（国内可达）；单次请求覆盖全部标的。"""

    name = "eastmoney"

    def fetch(self, client: httpx.Client,
              specs: list[str]) -> tuple[list[dict], list[str]]:
        parsed = [_parse_spec(spec) for spec in specs]
        rows: list[dict] = []
        errors: list[str] = []
        if not parsed:
            return rows, errors
        resp = client.get(
            EASTMONEY_URL,
            params={
                "fltt": "2",
                "fields": "f12,f13,f14,f2,f3",
                "secids": ",".join(code for _, _, code in parsed),
            },
            headers=EASTMONEY_HEADERS,
            timeout=15.0,
        )
        resp.raise_for_status()
        diff = (resp.json().get("data") or {}).get("diff") or []
        by_code = {f"{item['f13']}.{item['f12']}": item for item in diff}
        for asset_class, name, code in parsed:
            item = by_code.get(code)
            price = item.get("f2") if item else None
            if not item or price in (None, "-"):
                errors.append(f"{code} 未返回数据")
                continue
            change = item.get("f3")
            rows.append(
                {
                    "asset_code": code,
                    "asset_name": name or item.get("f14", ""),
                    "asset_class": asset_class,
                    "price": float(price),
                    "change_pct": None if change in (None, "-") else float(change),
                    "source": self.name,
                }
            )
        return rows, errors


class StooqCsvProvider:
    """备选免费行情 CSV 源；单资产失败不影响其它资产。"""

    name = "stooq"

    def fetch(self, client: httpx.Client,
              specs: list[str]) -> tuple[list[dict], list[str]]:
        rows: list[dict] = []
        errors: list[str] = []
        for spec in specs:
            asset_class, name, code = _parse_spec(spec)
            try:
                resp = client.get(STOOQ_URL.format(symbol=code), timeout=15.0)
                resp.raise_for_status()
                reader = csv.DictReader(io.StringIO(resp.text))
                data = next(reader, None)
                if data is None or not data.get("Close"):
                    raise RuntimeError(f"{code} 无数据")
                rows.append(
                    {
                        "asset_code": code,
                        "asset_name": name,
                        "asset_class": asset_class,
                        "price": float(data["Close"]),
                        "change_pct": None,
                        "source": self.name,
                    }
                )
            except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                errors.append(f"{spec}: {type(exc).__name__}: {exc}")
        return rows, errors


PROVIDERS = {
    "eastmoney": EastmoneyProvider,
    "stooq": StooqCsvProvider,
}


def get_market_provider(settings: Settings):
    cls = PROVIDERS.get(settings.market_provider)
    if cls is None:
        raise RuntimeError(f"未知行情 provider: {settings.market_provider}")
    return cls()


def _parse_symbols(raw: str) -> list[str]:
    return [s.strip() for s in raw.split(",") if s.strip()]


def run_snapshots(db: Session, settings: Settings, *,
                  client: httpx.Client | None = None) -> dict:
    symbols = _parse_symbols(settings.market_symbols)
    if not symbols:
        return {"fetched": 0, "errors": []}
    own = client is None
    client = client or httpx.Client(timeout=15.0)
    batch_id = uuid.uuid4().hex[:12]
    try:
        provider = get_market_provider(settings)
        try:
            rows, errors = provider.fetch(client, symbols)
        except Exception as exc:  # noqa: BLE001
            return {"fetched": 0, "errors": [f"{provider.name}: {type(exc).__name__}: {exc}"]}
        for row in rows:
            row["batch_id"] = batch_id
        snapshots_repo.insert_snapshots(db, rows)
        return {"fetched": len(rows), "errors": errors}
    finally:
        if own:
            client.close()
