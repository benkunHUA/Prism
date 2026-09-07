from datetime import datetime, timezone

from app.models.entities import Category
from app.repositories import analyses, articles, logs, sources, tasks


def _seed(client):
    with client.app.state.session_factory() as db:
        src = sources.create_source(
            db, name="S", url="https://example.com/rss", feed_type="rss", lang="en",
            categories=[Category.economy.value],
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        articles.insert_articles(db, [
            dict(source_id=src.id, category="economy", url="https://example.com/a",
                 title="Fed moves", summary="sum", content_text="body",
                 published_at=now, lang="en", dedupe_hash="ha"),
            dict(source_id=src.id, category="economy", url="https://example.com/b",
                 title="ECB moves", summary="sum", content_text="body",
                 published_at=now, lang="en", dedupe_hash="hb"),
        ])
        an = analyses.create_analysis(
            db, kind="daily", category="economy", title="经济每日分析",
            content_md="## 要点速览\n正文", period_start=now, period_end=now, model="fake",
        )
        ids = [a.id for a in articles.list_articles(db, category="economy")]
        analyses.link_articles(db, an, ids)
        task = tasks.create_task(db, name="采集", kind="collect", category=None, cron="0 */4 * * *")
        lg = logs.create_log(db, task.id)
        logs.finish_log(db, lg, status="success", fetched_count=2, new_count=2)
        return an.id


def test_content_endpoints(client):
    analysis_id = _seed(client)

    cats = client.get("/api/categories").json()
    economy = next(c for c in cats if c["category"] == "economy")
    assert economy["article_count"] >= 2

    art_resp = client.get("/api/categories/economy/articles?limit=10")
    assert art_resp.status_code == 200
    assert len(art_resp.json()["items"]) == 2

    detail = client.get(f"/api/analyses/{analysis_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["kind"] == "daily" and len(body["citations"]) == 2
    assert body["citations"][0]["url"].startswith("https://example.com/")

    dash = client.get("/api/dashboard/summary")
    assert dash.status_code == 200
    data = dash.json()
    assert data["today_articles"] >= 2 and data["today_analyses"] >= 1
    assert data["source_health"]["healthy"] >= 1
    assert data["next_run_at"] is not None

    logs_resp = client.get("/api/logs?limit=5")
    assert logs_resp.status_code == 200
    assert logs_resp.json()["items"][0]["status"] == "success"


def test_article_detail(client):
    _seed(client)
    article_id = client.get("/api/categories/economy/articles").json()["items"][0]["id"]
    body = client.get(f"/api/articles/{article_id}").json()
    assert body["title"] in ("Fed moves", "ECB moves")
