import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app

ALICE = "test-alice-" + "a" * 32
BOB = "test-bob-" + "b" * 32


def user(identity, key, permissions, enabled=True):
    return {"id": identity, "key_sha256": hashlib.sha256(key.encode()).hexdigest(),
            "enabled": enabled, "permissions": permissions}


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.delenv("LOGINEXUS_API_KEY", raising=False)
    monkeypatch.setenv("LOGINEXUS_REQUIRE_AUTH", "true")
    path = tmp_path / "users.json"
    path.write_text(json.dumps({"users": [
        user("alice", ALICE, ["analytics"]),
        user("bob", BOB, ["transport", "evaluation"]),
    ]}))
    monkeypatch.setenv("LOGINEXUS_API_USERS_FILE", str(path))
    return path


def test_independent_users_have_distinct_read_permissions(registry, tmp_path):
    with TestClient(create_app(tmp_path, tmp_path, tmp_path, tmp_path)) as client:
        for key, allowed, forbidden in (
            (ALICE, ["/ready", "/annual-kpis", "/annual-forecast"],
             ["/transport-plan", "/transport-plan/nodes", "/temporal-evaluation"]),
            (BOB, ["/transport-plan", "/transport-plan/nodes", "/temporal-evaluation",
                   "/temporal-evaluation/predictions"], ["/ready", "/annual-kpis"]),
        ):
            for endpoint in allowed:
                assert client.get(endpoint, headers={"X-API-Key": key}).status_code == 503
            for endpoint in forbidden:
                assert client.get(endpoint, headers={"X-API-Key": key}).status_code == 403
        assert client.get("/annual-kpis").status_code == 401
        assert client.get("/health").status_code == 200
        assert ALICE not in client.get("/openapi.json").text
        assert "key_sha256" not in client.get("/openapi.json").text


def test_disable_only_one_user_after_recreation(registry, tmp_path):
    config = json.loads(registry.read_text())
    config["users"][0]["enabled"] = False
    registry.write_text(json.dumps(config))
    with TestClient(create_app(tmp_path, tmp_path, tmp_path, tmp_path)) as client:
        assert client.get("/annual-kpis", headers={"X-API-Key": ALICE}).status_code == 401
        assert client.get("/transport-plan", headers={"X-API-Key": BOB}).status_code == 503


@pytest.mark.parametrize("config", [
    {}, {"users": []}, {"users": [user("a", ALICE, ["admin"])]},
    {"users": [user("a", ALICE, []), user("b", ALICE, [])]},
    {"users": [{"id": "a", "key_sha256": "bad", "enabled": True, "permissions": []}]},
])
def test_invalid_registry_fails_closed(registry, tmp_path, config):
    registry.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="configuration"):
        create_app(tmp_path, tmp_path, tmp_path, tmp_path)


def test_conflicting_shared_and_user_configuration_rejected(registry, tmp_path, monkeypatch):
    monkeypatch.setenv("LOGINEXUS_API_KEY", ALICE)
    with pytest.raises(ValueError, match="not both"):
        create_app(tmp_path, tmp_path, tmp_path, tmp_path)


def test_missing_user_registry_fails_closed(registry, tmp_path):
    registry.unlink()
    with pytest.raises(ValueError, match="configuration"):
        create_app(tmp_path, tmp_path, tmp_path, tmp_path)



def test_mounted_api_preserves_permission_boundaries(registry, tmp_path):
    from fastapi import FastAPI

    parent = FastAPI()
    parent.mount("/api", create_app(tmp_path, tmp_path, tmp_path, tmp_path))
    with TestClient(parent) as client:
        assert client.get("/api/transport-plan", headers={"X-API-Key": ALICE}).status_code == 403
        assert client.get("/api/transport-plan", headers={"X-API-Key": BOB}).status_code == 503
        assert client.get("/api/annual-kpis", headers={"X-API-Key": BOB}).status_code == 403
        assert client.get("/api/brazil/indicators", headers={"X-API-Key": BOB}).status_code == 403
        assert client.get("/api/brazil/gas-movements", headers={"X-API-Key": BOB}).status_code == 403
        assert client.get("/api/brazil/water-freight", headers={"X-API-Key": BOB}).status_code == 403
        assert client.get("/api/brazil/road-flows", headers={"X-API-Key": BOB}).status_code == 403
        assert client.get("/api/brazil/indicators", headers={"X-API-Key": ALICE}).status_code == 200
        assert client.get("/api/annual-kpis", headers={"X-API-Key": ALICE}).status_code == 503
        assert client.get("/api/temporal-evaluation", headers={"X-API-Key": ALICE}).status_code == 403
        assert client.get("/api/temporal-evaluation", headers={"X-API-Key": BOB}).status_code == 503


def test_unclassified_protected_route_denies_access(registry):
    from fastapi import APIRouter, FastAPI

    from freight_intelligence.api.security import authentication_dependencies

    app = FastAPI()
    router = APIRouter(dependencies=authentication_dependencies())

    @router.get("/new-data")
    def new_data():
        return {"private": True}

    app.include_router(router)
    with TestClient(app) as client:
        assert client.get("/new-data", headers={"X-API-Key": ALICE}).status_code == 403
        assert client.get("/new-data", headers={"X-API-Key": BOB}).status_code == 403
