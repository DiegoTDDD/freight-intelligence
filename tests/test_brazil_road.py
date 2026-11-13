import hashlib
import json
import shutil

import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_road import DEFAULT_ROOT, load_road, load_road_monthly
from scripts.prepare_brazil_road import prepare


def test_reviewed_regional_flows_and_reproducible_build(tmp_path):
    data, metadata = load_road()
    assert data.height == 16
    assert data.row(0, named=True)["tonnes"] == 14403113
    assert data.filter(data["origin_region"] == "Itaituba")["destination_region"].to_list() == ["Sinop", "Sorriso"]
    assert metadata["source"]["table"] == 12
    assert prepare(tmp_path) == 16
    assert (tmp_path / "regional_flows.csv").read_bytes() == (DEFAULT_ROOT / "regional_flows.csv").read_bytes()
    assert (tmp_path / "monthly.csv").read_bytes() == (DEFAULT_ROOT / "monthly.csv").read_bytes()
    assert metadata["reconciliation"]["annual_tonnes"] == 1368699651


@pytest.mark.parametrize("damage", ["hash", "negative", "duplicate", "state", "year"])
def test_invalid_road_snapshots_fail_closed(tmp_path, damage):
    root = tmp_path / "road"
    shutil.copytree(DEFAULT_ROOT, root)
    path = root / "regional_flows.csv"
    if damage == "hash":
        path.write_bytes(path.read_bytes() + b"x")
    else:
        import polars as pl

        data = pl.read_csv(path)
        if damage == "negative":
            data = data.with_columns(pl.lit(-1).alias("tonnes"))
        elif damage == "duplicate":
            data = pl.concat([data.head(15), data.head(1)])
        elif damage == "state":
            data = data.with_columns(pl.lit("ZZ").alias("origin_state"))
        else:
            data = data.with_columns(pl.lit(2050).alias("year"))
        raw = data.write_csv().encode()
        path.write_bytes(raw)
        metadata_path = root / "provenance.json"
        metadata = json.loads(metadata_path.read_bytes())
        metadata["files"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
        metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        load_road(root)


def test_road_api_scoped_filters_and_unavailable(tmp_path):
    with TestClient(create_app()) as client:
        result = client.get("/brazil/road-flows?origin_state=PA&destination_state=MT&same_region=false")
        assert result.status_code == 200 and result.json()["count"] == 2
        assert {row["origin_region"] for row in result.json()["data"]} == {"Itaituba"}
        assert client.get("/brazil/road-flows?origin_state=ZZ").status_code == 422
        assert client.get("/brazil/road-flows?origin_state=AC").json()["count"] == 0
        same = client.get("/brazil/road-flows?same_region=true").json()["data"]
        assert all(row["origin_region"] == row["destination_region"] for row in same)
    with TestClient(create_app(road_dir=tmp_path)) as client:
        assert client.get("/brazil/road-flows").status_code == 503


def test_annual_total_uses_months_and_not_regional_reference():
    data, metadata = load_road_monthly()
    assert data["month"].to_list() == list(range(1, 13))
    assert data["tonnes"].sum() == 1368699651
    assert data["tonnes"][0] == 97725063
    assert data["tonnes"][-1] == 102668585
    assert round(data["tonnes"].sum() / 1e9, 1) == 1.4
    assert metadata["reconciliation"]["regional_reference_tonnes"] == 1165000000
    assert metadata["reconciliation"]["annual_tonnes"] != 1165000000
    with TestClient(create_app()) as client:
        result = client.get("/brazil/road-monthly?month=1").json()
        assert result["count"] == 1 and result["data"][0]["tonnes"] == 97725063
        assert result["annual_reconciliation"]["annual_tonnes"] == 1368699651
        assert client.get("/brazil/road-monthly?month=13").status_code == 422


@pytest.mark.parametrize("damage", ["missing_month", "duplicate_month", "annual_mismatch"])
def test_monthly_reconciliation_rejects_incomplete_or_changed_series(tmp_path, damage):
    import polars as pl

    root = tmp_path / "road"
    shutil.copytree(DEFAULT_ROOT, root)
    path = root / "monthly.csv"
    data = pl.read_csv(path)
    if damage == "missing_month":
        data = data.head(11)
    elif damage == "duplicate_month":
        data = pl.concat([data.head(11), data.head(1)])
    else:
        data = data.with_columns((pl.col("tonnes") + 1).alias("tonnes"))
    raw = data.write_csv().encode()
    path.write_bytes(raw)
    metadata_path = root / "provenance.json"
    metadata = json.loads(metadata_path.read_bytes())
    metadata["files"][1]["sha256"] = hashlib.sha256(raw).hexdigest()
    metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        load_road_monthly(root)
    with TestClient(create_app(road_dir=root)) as client:
        assert client.get("/brazil/road-monthly").status_code == 503
