import hashlib
import json

import polars as pl
import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.optimization.transport import PROJECT_ROOT, solve_transport


@pytest.fixture
def transport_api(tmp_path):
    raw = (PROJECT_ROOT / "docs/examples/transport_scenario.json").read_bytes()
    arcs, nodes, summary = solve_transport(json.loads(raw))
    summary.update(
        {"input_sha256": hashlib.sha256(raw).hexdigest(), "input": "private/path/scenario.json"}
    )
    arcs.write_parquet(tmp_path / "allocation.parquet")
    nodes.write_parquet(tmp_path / "node_balances.parquet")
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    with TestClient(create_app(transport_dir=tmp_path)) as client:
        yield client, tmp_path


def test_saved_plan_summary_and_source_privacy(transport_api):
    client, _ = transport_api
    response = client.get("/transport-plan")
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total_cost"] == 190
    assert "Not a road itinerary" in body["summary"]["interpretation"]
    assert "input" not in body["summary"]
    assert "private/path" not in response.text
    assert body["total"] == body["count"] == 4
    assert [row["arc_id"] for row in body["data"]] == ["a-x", "a-y", "b-x", "b-y"]


def test_filters_pagination_and_empty_pages(transport_api):
    client, _ = transport_api
    body = client.get("/transport-plan?origin=supply-a&limit=1&offset=1").json()
    assert body["total"] == 2
    assert body["count"] == 1
    assert body["data"][0]["arc_id"] == "a-y"
    assert client.get("/transport-plan?destination=demand-x&active_only=true").json()["total"] == 1
    assert client.get("/transport-plan?offset=999").json()["data"] == []
    assert client.get("/transport-plan?origin=../../unknown").json()["total"] == 0


def test_node_balances_and_read_only_routes(transport_api):
    client, _ = transport_api
    body = client.get("/transport-plan/nodes?limit=2&offset=1").json()
    assert body["total"] == 4 and body["count"] == 2
    assert all(abs(row["residual"]) < 1e-7 for row in body["data"])
    assert client.post("/transport-plan", json={}).status_code == 405


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=1001", "offset=-1", "origin=", "active_only=unknown"]
)
def test_invalid_query_returns_422(transport_api, query):
    client, _ = transport_api
    assert client.get("/transport-plan?" + query).status_code == 422


@pytest.mark.parametrize(
    "filename", ["summary.json", "allocation.parquet", "node_balances.parquet"]
)
def test_incomplete_bundle_returns_503(transport_api, filename):
    client, path = transport_api
    (path / filename).unlink()
    response = client.get("/transport-plan")
    assert response.status_code == 503
    assert str(path) not in response.text
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize(
    "column,value",
    [
        ("flow", 999.0),
        ("flow", float("nan")),
        ("total_cost", 999.0),
        ("utilization", 0.5),
        ("destination", "missing"),
        ("arc_id", "same"),
    ],
)
def test_inconsistent_allocation_is_rejected(transport_api, column, value):
    client, path = transport_api
    file = path / "allocation.parquet"
    pl.read_parquet(file).with_columns(pl.lit(value).alias(column)).write_parquet(file)
    assert client.get("/transport-plan").status_code == 503
    assert client.get("/transport-plan/nodes").status_code == 503


def test_node_conservation_is_verified(transport_api):
    client, path = transport_api
    file = path / "node_balances.parquet"
    pl.read_parquet(file).with_columns(pl.lit(0.0).alias("balance")).write_parquet(file)
    assert client.get("/transport-plan").status_code == 503


def test_malformed_summary_and_mismatched_objective(transport_api):
    client, path = transport_api
    file = path / "summary.json"
    summary = json.loads(file.read_text())
    file.write_text("{")
    assert client.get("/transport-plan").status_code == 503
    summary["total_cost"] = 1.0
    file.write_text(json.dumps(summary))
    assert client.get("/transport-plan").status_code == 503


def test_serving_does_not_invoke_solver(transport_api, monkeypatch):
    import freight_intelligence.optimization.transport as optimizer

    client, _ = transport_api

    def fail(*args, **kwargs):
        raise AssertionError("API must not solve scenarios")

    monkeypatch.setattr(optimizer, "linprog", fail)
    assert client.get("/transport-plan").status_code == 200
