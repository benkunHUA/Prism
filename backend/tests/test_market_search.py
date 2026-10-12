import httpx

from app.services.market_search import resolve, search_assets, to_spec

SUGGEST_PAYLOAD = {
    "QuotationCodeTable": {
        "Data": [
            {"QuoteID": "112.B00Y", "Name": "布伦特原油当月连续",
             "SecurityTypeName": "期货", "MktNum": "112"},
            {"QuoteID": "102.CL00Y", "Name": "NYMEX原油",
             "SecurityTypeName": "期货", "MktNum": "102"},
        ]
    }
}
QUOTE_PAYLOAD = {
    "data": {
        "diff": [
            {"f12": "B00Y", "f13": 112, "f14": "布伦特原油当月连续", "f2": 106.91, "f3": 2.09},
            {"f12": "CL00Y", "f13": 102, "f14": "NYMEX原油", "f2": "-", "f3": "-"},
        ]
    }
}


def _client():
    def handler(request):
        if "suggest" in request.url.path:
            return httpx.Response(200, json=SUGGEST_PAYLOAD)
        return httpx.Response(200, json=QUOTE_PAYLOAD)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_search_assets_parses_candidates():
    rows = search_assets("原油", client=_client())
    assert [r["secid"] for r in rows] == ["112.B00Y", "102.CL00Y"]
    assert rows[0]["name"] == "布伦特原油当月连续"
    assert rows[0]["type_name"] == "期货"


def test_resolve_keeps_only_candidates_with_quote():
    rows = resolve("原油", client=_client())
    assert rows[0]["quote"] == {"name": "布伦特原油当月连续", "price": 106.91, "change_pct": 2.09}
    assert rows[1]["quote"] is None


def test_to_spec_escapes_separators():
    assert to_spec("commodity", "布伦特原油", "112.B00Y") == "commodity|布伦特原油=112.B00Y"
    assert to_spec("commodity", "A,B|C=D", "1.X") == "commodity|A，B C D=1.X"
