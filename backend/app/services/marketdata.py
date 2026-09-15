from __future__ import annotations

import csv
import io
import uuid

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories import snapshots as snapshots_repo

STOOQ_URL = "https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"


class StooqCsvProvider:
    """免费行情 CSV 源；单资产失败抛 httpx.HTTPError，由调用方降级。"""

    name = "stooq"

    def fetch(self, client: httpx.Client, specs: list[str]) -> list[dict]:
        rows = []
        for spec in specs:
            asset_class, name, code = self._parse_spec(spec)
            resp = client.get(STOOQ_URL.format(symbol=code), timeout=15.0)
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            data = next(reader, None)
            if data is None:
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
        return rows

    @staticmethod
    def _parse_spec(spec: str) -> tuple[str, str, str]:
        # 形如 "index|标普500=^spx" 或 "标普500=^spx"（默认 index）
        head, _, code = spec.partition("=")
        code = code.strip()
        if "|" in head:
            asset_class, name = head.split("|", 1)
        else:
            asset_class, name = "index", head
        return asset_class.strip(), name.strip(), code


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
        rows: list[dict] = []
        errors: list[str] = []
        for spec in symbols:
            try:
                rows.extend(StooqCsvProvider().fetch(client, [spec]))
            except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                errors.append(f"{spec}: {type(exc).__name__}: {exc}")
        for row in rows:
            row["batch_id"] = batch_id
        snapshots_repo.insert_snapshots(db, rows)
        return {"fetched": len(rows), "errors": errors}
    finally:
        if own:
            client.close()
