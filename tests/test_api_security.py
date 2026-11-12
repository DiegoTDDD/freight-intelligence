import polars as pl
import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app

KEY = "test-only-key-" + "x" * 32


@pytest.fixture(autouse=True)
def clear_auth_environment(monkeypatch):
    monkeypatch.delenv("LOGINEXUS_API_KEY", raising=False)
    monkeypatch.delenv("LOGINEXUS_REQUIRE_AUTH", raising=False)


@pytest.fixture
def protected(tmp_path, monkeypatch):
    pl.DataFrame({"metric_type": ["tons"], "year": [2050], "total_value": [10.0]}).write_parquet(
        tmp_path / "annual_kpis.parquet"
    )
    monkeypatch.setenv("LOGINEXUS_API_KEY", KEY)
    monkeypatch.setenv("LOGINEXUS_REQUIRE_AUTH", "true")
    with TestClient(create_app(tmp_path, tmp_path, tmp_path)) as client:
        yield client


@pytest.mark.parametrize(
    "endpoint",
    [
        "/ready",
        "/annual-kpis",
        "/annual-forecast",
        "/transport-plan",
        "/transport-plan/nodes",
        "/temporal-evaluation",
        "/temporal-evaluation/predictions",
    ],
)
def test_all_data_endpoints_require_key(protected, endpoint):
    for headers in ({}, {"X-API-Key": "wrong"}):
        response = protected.get(endpoint, headers=headers)
        assert response.status_code == 401
        assert KEY not in response.text
        assert response.headers["www-authenticate"] == "APIKey"


def test_valid_key_allows_data_and_normal_unavailable_responses(protected):
    headers = {"X-API-Key": KEY}
    assert protected.get("/ready", headers=headers).status_code == 200
    assert protected.get("/annual-kpis", headers=headers).json()["count"] == 1
    assert protected.get("/annual-forecast", headers=headers).status_code == 503
    assert protected.get("/transport-plan", headers=headers).status_code == 503


def test_health_and_documentation_remain_public(protected):
    assert protected.get("/health").json() == {"status": "ok"}
    assert protected.get("/docs").status_code == 200
    response = protected.get("/openapi.json")
    assert KEY not in response.text
    schema = response.json()
    assert schema["components"]["securitySchemes"]["LogiNexusAPIKey"]["name"] == "X-API-Key"
    assert schema["paths"]["/annual-kpis"]["get"]["security"] == [{"LogiNexusAPIKey": []}]
    assert "security" not in schema["paths"]["/health"]["get"]


def test_query_string_cannot_supply_credentials(protected):
    assert protected.get("/annual-kpis", params={"api_key": KEY}).status_code == 401


def test_changing_environment_requires_app_recreation(protected, monkeypatch):
    monkeypatch.setenv("LOGINEXUS_API_KEY", "replacement-" + "y" * 32)
    assert protected.get("/annual-kpis", headers={"X-API-Key": KEY}).status_code == 200


def test_local_defaults_do_not_require_authentication(tmp_path):
    with TestClient(create_app(tmp_path, tmp_path, tmp_path)) as client:
        assert client.get("/annual-kpis").status_code == 503
        assert "LogiNexusAPIKey" not in client.get("/openapi.json").text


def test_configured_key_enforces_auth_even_when_require_flag_is_false(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGINEXUS_API_KEY", KEY)
    monkeypatch.setenv("LOGINEXUS_REQUIRE_AUTH", "false")
    with TestClient(create_app(tmp_path, tmp_path, tmp_path)) as client:
        assert client.get("/annual-kpis").status_code == 401


@pytest.mark.parametrize(
    "flag,key",
    [
        ("true", ""),
        ("invalid", KEY),
        ("true", "short"),
        ("false", " " * 40),
        ("true", "é" * 40),
        ("true", "x" * 32 + "\n"),
    ],
)
def test_bad_configuration_prevents_startup(tmp_path, monkeypatch, flag, key):
    monkeypatch.setenv("LOGINEXUS_REQUIRE_AUTH", flag)
    monkeypatch.setenv("LOGINEXUS_API_KEY", key)
    with pytest.raises(ValueError) as error:
        create_app(tmp_path, tmp_path, tmp_path)
    if key:
        assert key not in str(error.value)
