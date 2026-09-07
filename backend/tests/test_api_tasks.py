def test_task_crud_and_manual_run(client, monkeypatch):
    from app.api import routes_tasks

    listed = client.get("/api/tasks").json()["items"]
    assert len(listed) == 2  # 种子默认任务

    body = {"name": "军事采集", "kind": "collect", "category": "military", "cron": "0 */6 * * *"}
    created = client.post("/api/tasks", json=body)
    assert created.status_code == 201
    task_id = created.json()["id"]

    patched = client.patch(f"/api/tasks/{task_id}", json={"enabled": False})
    assert patched.status_code == 200 and patched.json()["enabled"] is False

    monkeypatch.setattr(
        routes_tasks, "run_task_flow",
        lambda db, task, **kwargs: {"task_id": task.id, "status": "success",
                                    "fetched": 5, "new": 4, "errors": []},
    )
    run = client.post(f"/api/tasks/{task_id}/run")
    assert run.status_code == 200
    assert run.json()["status"] == "success" and run.json()["new"] == 4

    assert client.delete(f"/api/tasks/{task_id}").status_code == 204
    assert client.get(f"/api/tasks/{task_id}").status_code == 404


def test_manual_run_missing_task_404(client):
    assert client.post("/api/tasks/99999/run").status_code == 404
