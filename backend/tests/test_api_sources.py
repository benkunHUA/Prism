def test_list_and_create_source(client):
    resp = client.get("/api/sources")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 10  # 种子源

    body = {
        "name": "Test Feed", "url": "https://test.example/feed",
        "feed_type": "rss", "lang": "en", "categories": ["finance"],
    }
    created = client.post("/api/sources", json=body)
    assert created.status_code == 201
    data = created.json()
    assert data["categories"] == ["finance"] and data["enabled"] is True

    dup = client.post("/api/sources", json=body)
    assert dup.status_code == 409


def test_patch_and_delete_source(client):
    source_id = client.get("/api/sources").json()["items"][0]["id"]
    resp = client.patch(f"/api/sources/{source_id}", json={"enabled": False, "categories": ["economy"]})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["categories"] == ["economy"]
    assert client.delete(f"/api/sources/{source_id}").status_code == 204
    assert client.get(f"/api/sources/{source_id}").status_code == 404


def test_source_test_endpoint(client, monkeypatch):
    from app.api import routes_sources

    def fake_fetch(source, settings, http):
        return (
            [{"url": "https://x.test/a", "title": "T", "published_at": None}],
            None,
        )

    monkeypatch.setattr(routes_sources, "fetch_source", fake_fetch)
    source_id = client.get("/api/sources").json()["items"][0]["id"]
    resp = client.post(f"/api/sources/{source_id}/test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True and body["preview"][0]["title"] == "T"
