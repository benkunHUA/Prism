from fastapi.testclient import TestClient

from app.api.static_site import _within
from app.core.config import Settings
from app.main import create_app


def _dist(tmp_path):
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (root / "assets" / "index.js").write_text("console.log(1)", encoding="utf-8")
    return root


def _client(tmp_path) -> TestClient:
    settings = Settings(
        _env_file=None, db_path=str(tmp_path / "api.db"), scheduler_enabled=False,
        static_dir=str(_dist(tmp_path)),
    )
    return TestClient(create_app(settings))


def test_spa_serves_index_assets_and_keeps_api(tmp_path):
    with _client(tmp_path) as c:
        assert c.get("/").text == "<html>app</html>"
        assert c.get("/boards/whatever").text == "<html>app</html>"
        assert c.get("/assets/index.js").text == "console.log(1)"
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/nope").status_code == 404


def test_spa_absent_without_static_dir(tmp_path):
    settings = Settings(
        _env_file=None, db_path=str(tmp_path / "api.db"), scheduler_enabled=False
    )
    with TestClient(create_app(settings)) as c:
        assert c.get("/").status_code == 404


def test_within_rejects_path_escape(tmp_path):
    root = tmp_path / "dist"
    root.mkdir()
    (root / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("y", encoding="utf-8")

    assert _within(root, "a.txt") is not None
    assert _within(root, "../outside.txt") is None
