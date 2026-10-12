from pathlib import Path

import httpx

from app.core.config import Settings
from app.services.marketdata import EastmoneyProvider, StooqCsvProvider, run_snapshots

STOOQ_FIXTURE = Path(__file__).parent / "data" / "stooq_fixture.csv"
EM_FIXTURE = Path(__file__).parent / "data" / "eastmoney_fixture.json"


def _stooq_client():
    content = STOOQ_FIXTURE.read_bytes()

    def handler(request):
        if "^spx" in str(request.url):
            return httpx.Response(200, content=content)
        raise httpx.ConnectError("boom", request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _eastmoney_client():
    payload = EM_FIXTURE.read_bytes()
    return httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=payload))
    )


def test_eastmoney_provider_batches_and_reports_missing():
    rows, errors = EastmoneyProvider().fetch(
        _eastmoney_client(),
        [
            "index|标普500=100.SPX",
            "commodity|伦敦金=101.GC00Y",
            "index|不存在=100.NOPE",
        ],
    )
    assert [r["asset_code"] for r in rows] == ["100.SPX", "101.GC00Y"]
    assert rows[0]["price"] == 7584.64 and rows[0]["change_pct"] == -0.46
    assert len(errors) == 1 and "100.NOPE" in errors[0]


def test_stooq_provider_parses_csv():
    rows, errors = StooqCsvProvider().fetch(_stooq_client(), ["标普500=^spx"])
    assert errors == []
    assert rows[0]["asset_code"] == "^spx"
    assert rows[0]["price"] == 5980.0


def test_run_snapshots_eastmoney_default(db):
    settings = Settings(
        _env_file=None,
        market_symbols="index|标普500=100.SPX,commodity|伦敦金=101.GC00Y",
    )
    result = run_snapshots(db, settings, client=_eastmoney_client())
    assert result["fetched"] == 2 and result["errors"] == []
    from app.repositories import snapshots

    assert snapshots.latest_batch_id(db) is not None
    assert {s.asset_code for s in snapshots.list_snapshots(db)} == {"100.SPX", "101.GC00Y"}


def test_run_snapshots_stooq_degrades(db):
    settings = Settings(
        _env_file=None,
        market_provider="stooq",
        market_symbols="index|标普500=^spx,rate|美债10Y=10usy.b",
    )
    result = run_snapshots(db, settings, client=_stooq_client())
    assert result["fetched"] == 1
    assert len(result["errors"]) == 1
