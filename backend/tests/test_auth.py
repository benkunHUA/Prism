import base64

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _client(tmp_path, **overrides) -> TestClient:
    settings = Settings(
        _env_file=None, db_path=str(tmp_path / "api.db"), scheduler_enabled=False, **overrides
    )
    return TestClient(create_app(settings))


def _header(user: str, password: str) -> dict:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_auth_disabled_when_password_empty(tmp_path):
    with _client(tmp_path) as c:
        assert c.get("/api/health").status_code == 200


def test_auth_challenges_and_accepts(tmp_path):
    with _client(tmp_path, auth_user="u", auth_password="p") as c:
        denied = c.get("/api/health")
        assert denied.status_code == 401
        assert denied.headers["www-authenticate"].startswith("Basic")
        assert c.get("/api/health", headers=_header("u", "p")).status_code == 200
        assert c.get("/api/health", headers=_header("u", "bad")).status_code == 401
        assert c.get("/api/health", headers=_header("bad", "p")).status_code == 401


def test_auth_rejects_malformed_header(tmp_path):
    with _client(tmp_path, auth_user="u", auth_password="p") as c:
        for value in ("Bearer x", "Basic", "Basic !!!not-base64"):
            assert c.get("/api/health", headers={"Authorization": value}).status_code == 401
