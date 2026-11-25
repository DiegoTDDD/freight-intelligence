import hashlib
import subprocess
import sys

from fastapi.testclient import TestClient

from freight_intelligence.api.public_snapshot import PROJECT, snapshot_api
from freight_intelligence.public_api import create_public_app


def test_independent_public_api_has_reviewed_data_no_private_plan_and_revision(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "a" * 40)
    with TestClient(create_public_app()) as client:
        assert client.get("/").url.path == "/docs"
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").status_code == 200
        version = client.get("/version").json()
        assert version["revision"] == "a" * 40
        assert version["snapshot_manifest_sha256"] == hashlib.sha256((PROJECT / "deployment/preview_data/snapshot_manifest.json").read_bytes()).hexdigest()
        assert client.get("/annual-kpis?metric_type=tons").json()["count"] > 0
        assert client.get("/brazil/air-freight?view=pairs&limit=1").status_code == 200
        assert client.get("/brazil/duty-review?example=unknown_regime").json()["review"]["status"] == "manual_review_required"
        assert client.get("/transport-plan").status_code == 503
        assert client.post("/annual-kpis", json={}).status_code == 405


def test_no_streamlit_import_or_server_is_needed():
    code = "import sys; import freight_intelligence.public_api; assert 'streamlit' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True, timeout=30)


def test_missing_public_data_does_not_fall_back_to_local_gold(tmp_path):
    with TestClient(create_public_app(tmp_path)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
        assert client.get("/version").status_code == 503
        assert client.get("/annual-kpis").status_code == 503


def test_public_mode_still_honors_configured_authentication(monkeypatch):
    key = "separate-api-test-" + "x" * 32
    monkeypatch.setenv("LOGINEXUS_REQUIRE_AUTH", "true")
    monkeypatch.setenv("LOGINEXUS_API_KEY", key)
    with TestClient(create_public_app()) as client:
        assert client.get("/annual-kpis").status_code == 401
        assert client.get("/annual-kpis", headers={"X-API-Key": key}).status_code == 200


def test_independent_reader_has_same_analytical_contract_as_dashboard():
    root = PROJECT / "deployment/preview_data"
    with TestClient(create_public_app(root)) as separate, TestClient(snapshot_api(root)) as mounted:
        for path in ("/annual-kpis", "/annual-forecast", "/brazil/indicators?mode=rail", "/brazil/duty-review"):
            assert separate.get(path).json() == mounted.get(path).json()


def test_version_never_discloses_arbitrary_environment_content(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "not-a-revision-or-a-secret")
    with TestClient(create_public_app()) as client:
        assert client.get("/version").json()["revision"] == "unknown"
