"""Public mount contracts, snapshot isolation and authentication regression."""

from pathlib import Path

from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Mount

from freight_intelligence.hosted_app import snapshot_api

SNAPSHOT = Path(__file__).resolve().parents[1] / "deployment/preview_data"


def client_for(root):
    return TestClient(Starlette(routes=[Mount("/api", app=snapshot_api(root))]))


def test_public_snapshot_mount():
    with client_for(SNAPSHOT) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/ready").status_code == 200
        assert client.get("/api/docs").status_code == 200
        spec = client.get("/api/openapi.json").json()
        assert {"url": "/api"} in spec["servers"]
        for endpoint in ("annual-kpis", "annual-forecast", "temporal-evaluation"):
            response = client.get(f"/api/{endpoint}?metric_type=tons")
            assert response.status_code == 200, response.text
        assert client.get("/api/annual-kpis?metric_type=invalid").status_code == 422
        # Private local plans must never be picked up as a fallback.
        assert client.get("/api/transport-plan").status_code == 503
        assert client.post("/api/annual-kpis", json={}).status_code == 405


def test_missing_snapshot_never_falls_back_to_project_data(tmp_path):
    with client_for(tmp_path) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/ready").status_code == 503
        assert client.get("/api/annual-forecast").status_code == 503
        assert client.get("/api/temporal-evaluation").status_code == 503


def test_hosted_mount_preserves_required_authentication(monkeypatch):
    monkeypatch.setenv("LOGINEXUS_REQUIRE_AUTH", "true")
    monkeypatch.setenv("LOGINEXUS_API_KEY", "hosted-test-key-" + "x" * 32)
    with client_for(SNAPSHOT) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/annual-kpis").status_code == 401
        assert client.get(
            "/api/annual-kpis", headers={"X-API-Key": "hosted-test-key-" + "x" * 32}
        ).status_code == 200
