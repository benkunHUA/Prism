from pathlib import Path

import httpx

from app.core.config import Settings
from app.services.marketdata import StooqCsvProvider, run_snapshots

FIXTURE = Path(__file__).parent / "data" / "stooq_fixture.csv"


def _client_for_csv():
    content = FIXTURE.read_bytes()

    def handler(request):
        if "^spx" in str(request.url):
            return httpx.Response(200, content=content)
        raise httpx.ConnectError("boom", request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_stooq_provider_parses_csv():
    provider = StooqCsvProvider()
    rows = provider.fetch(_client_for_csv(), ["标普500=^spx"])
    assert rows[0]["asset_code"] == "^spx"
    assert rows[0]["price"] == 5980.0


def test_run_snapshots_inserts_batch_and_degrades(db):
    settings = Settings(_env_file=None, market_symbols="index|标普500=^spx,rate|美债10Y=10usy.b")
    result = run_snapshots(db, settings, client=_client_for_csv())
    assert result["fetched"] == 1
    assert len(result["errors"]) == 1
    from app.repositories import snapshots

    assert snapshots.latest_batch_id(db) is not None
    assert snapshots.list_snapshots(db)[0].price == 5980.0
