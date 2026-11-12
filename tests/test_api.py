import polars as pl
import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.ml.annual_forecast import main as forecast_main


@pytest.fixture
def api(tmp_path):
    gold = tmp_path / "gold"
    models = tmp_path / "models"
    gold.mkdir()
    models.mkdir()
    data = pl.DataFrame(
        {
            "metric_type": ["tons"] * 5 + ["value"] * 5,
            "year": [2017, 2020, 2025, 2030, 2050] * 2,
            "total_value": [100.0, 120.0, 150.0, 180.0, 300.0] * 2,
        }
    )
    data.write_parquet(gold / "annual_kpis.parquet")
    forecast_main([
        "--input", str(gold / "annual_kpis.parquet"), "--output-dir", str(models),
        "--end-year", "2052", "--holdout-points", "2",
    ])
    with TestClient(create_app(gold, models)) as client:
        yield client, gold, models


def test_health_does_not_require_data(tmp_path):
    with TestClient(create_app(tmp_path, tmp_path)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").status_code == 503


def test_annual_filters_and_readiness(api):
    client, _, _ = api
    assert client.get("/ready").status_code == 200
    response = client.get(
        "/annual-kpis",
        params={
            "metric_type": "tons",
            "start_year": 2020,
            "end_year": 2030,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert [row["year"] for row in body["data"]] == [2020, 2025, 2030]
    assert {row["metric_type"] for row in body["data"]} == {"tons"}
    assert "projected" in body["source"]


def test_forecast_includes_interpretation(api):
    client, _, _ = api
    body = client.get("/annual-forecast?metric_type=tons").json()
    assert body["count"] == 2
    assert "not accuracy against future observed" in body["interpretation"]
    assert {row["result_type"] for row in body["data"]} == {"faf_scenario_extrapolation"}


@pytest.mark.parametrize(
    "url",
    [
        "/annual-kpis?metric_type=unknown",
        "/annual-kpis?start_year=2050&end_year=2020",
        "/annual-kpis?start_year=abc",
        "/annual-forecast?metric_type=unknown",
    ],
)
def test_invalid_queries_return_422(api, url):
    client, _, _ = api
    assert client.get(url).status_code == 422


def test_empty_filter_is_successful(api):
    client, _, _ = api
    response = client.get("/annual-kpis?metric_type=tmiles")
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_missing_forecast_does_not_block_annual_indicators(api):
    client, _, models = api
    (models / "forecast.parquet").unlink()
    response = client.get("/annual-forecast")
    assert response.status_code == 503
    assert str(models) not in response.text
    assert client.get("/annual-kpis").status_code == 200
    assert client.get("/ready").status_code == 200


def test_corrupt_or_wrong_schema_returns_503(api):
    client, gold, _ = api
    source = gold / "annual_kpis.parquet"
    source.write_bytes(b"not a parquet")
    assert client.get("/annual-kpis").status_code == 503
    pl.DataFrame({"unexpected": [1]}).write_parquet(source)
    assert client.get("/ready").status_code == 503


def test_openapi_and_read_only_routes(api):
    client, _, _ = api
    schema = client.get("/openapi.json").json()
    assert "/annual-forecast" in schema["paths"]
    assert client.post("/annual-kpis", json={}).status_code == 405


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0, None])
def test_invalid_numeric_data_returns_503_instead_of_serialization_error(api, value):
    client, gold, _ = api
    pl.DataFrame({"metric_type": ["tons"], "year": [2050], "total_value": [value]}).write_parquet(
        gold / "annual_kpis.parquet"
    )
    assert client.get("/annual-kpis").status_code == 503


def test_forecast_rejects_stale_source_without_blocking_indicators(api):
    client, gold, _ = api
    path = gold / "annual_kpis.parquet"
    pl.read_parquet(path).with_columns((pl.col("total_value") + 1).alias("total_value")).write_parquet(path)
    response = client.get("/annual-forecast")
    assert response.status_code == 503
    assert str(gold) not in response.text
    assert client.get("/annual-kpis").status_code == 200


@pytest.mark.parametrize("corruption", ["metadata", "selection", "duplicate_year"])
def test_forecast_validates_entire_saved_bundle(api, corruption):
    client, _, models = api
    if corruption == "metadata":
        (models / "metadata.json").unlink()
    elif corruption == "selection":
        path = models / "evaluation.parquet"
        pl.read_parquet(path).with_columns(pl.lit(False).alias("selected")).write_parquet(path)
    else:
        path = models / "forecast.parquet"
        frame = pl.read_parquet(path)
        pl.concat([frame, frame.head(1)]).write_parquet(path)
    assert client.get("/annual-forecast").status_code == 503
