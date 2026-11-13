import hashlib
import json
import shutil

import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_road import DEFAULT_ROOT, load_road
from scripts.prepare_brazil_road import prepare


def test_reviewed_regional_flows_and_reproducible_build(tmp_path):
    data, metadata = load_road()
    assert data.height == 16
    assert data.row(0, named=True)["tonnes"] == 14403113
    assert data.filter(data["origin_region"] == "Itaituba")["destination_region"].to_list() == ["Sinop", "Sorriso"]
    assert metadata["source"]["table"] == 12
    assert prepare(tmp_path) == 16
    assert (tmp_path / "regional_flows.csv").read_bytes() == (DEFAULT_ROOT / "regional_flows.csv").read_bytes()
    assert "unreconciled" in " ".join(metadata["quality_notes"])


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
