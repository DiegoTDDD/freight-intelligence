import hashlib
import json
import shutil

import polars as pl
import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_water_ports import (
    DEFAULT_ROOT,
    load_port_pairs,
    read_contract,
    validate,
)
from scripts.prepare_brazil_water_ports import prepare


def test_original_port_exports_rebuild_and_reconcile(tmp_path):
    shutil.copytree(DEFAULT_ROOT, tmp_path / "water")
    root = tmp_path / "water"
    before = (root / "port_pairs.csv").read_bytes()
    prepare(root)
    assert (root / "port_pairs.csv").read_bytes() == before
    data, _ = load_port_pairs(root)
    assert data.height == 510
    for contract in read_contract()["origins"].values():
        rows = data.filter(pl.col("origin_port") == contract["origin_port"])
        assert rows.height == contract["rows"]
        assert rows["tonnes"].sum() == pytest.approx(contract["tonnes"], abs=1e-6)


@pytest.mark.parametrize("defect", ["period", "total", "source", "context"])
def test_port_pairs_fail_closed_after_tampering(tmp_path, defect):
    root = tmp_path / "water"
    shutil.copytree(DEFAULT_ROOT, root)
    load_port_pairs(root)  # A populated cache must invalidate when original evidence changes.
    path = root / "port_pairs_provenance.json"
    metadata = json.loads(path.read_bytes())
    if defect == "period":
        metadata["filters"]["year"] = [2026]
    else:
        name = {"total": "port_pairs.csv", "source": "port_pairs_santos_2025.xlsx",
                "context": "port_pairs_santos_2025_context.jpg"}[defect]
        target = root / name
        if defect == "total":
            pl.read_csv(target).with_columns((pl.col("tonnes") * 2).alias("tonnes")).write_csv(target)
        else:
            target.write_bytes(b"changed evidence")
        next(record for record in metadata["files"] if record["path"] == name)["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        load_port_pairs(root)


def test_destination_margins_detect_redistribution_that_preserves_origin_total():
    data, _ = load_port_pairs()
    changed = data.with_columns(
        pl.when((pl.col("origin_port") == "Santos") & (pl.col("destination_port") == "Suape"))
        .then(pl.col("tonnes") + 1)
        .when((pl.col("origin_port") == "Santos") & (pl.col("destination_port") == "Vitória"))
        .then(pl.col("tonnes") - 1).otherwise(pl.col("tonnes")).alias("tonnes")
    )
    with pytest.raises(ValueError, match="destination"):
        validate(changed, read_contract())


def test_all_reviewed_categories_and_small_source_flows_are_retained():
    data, metadata = load_port_pairs()
    assert data["origin_port"].n_unique() == metadata["origin_count"] == 98
    assert data.select("destination_state", "destination_port").unique().height == 71
    assert data.filter(pl.col("origin_port") == "Altamira")["tonnes"].sum() == 4.5
    assert data.filter(pl.col("origin_port") == "Não Identificado")["tonnes"].sum() == 96
    assert data.filter(pl.col("origin_port") == "Bacia Sedimentar de Santos")["origin_state"].unique().to_list() == ["ZEE/Plat. Continental"]


def test_port_pair_api_pagination_filters_and_missing_source(tmp_path):
    with TestClient(create_app()) as client:
        result = client.get("/brazil/water-port-pairs").json()
        assert result["total"] == 510 and result["count"] == 100
        assert client.get("/brazil/water-port-pairs?limit=500&offset=500").json()["count"] == 10
        result = client.get("/brazil/water-port-pairs?origin_port=Santos&limit=1&offset=1").json()
        assert result["total"] == 30 and result["count"] == 1
        assert result["filtered_tonnes"] == pytest.approx(8790074.053)
        assert result["data"][0]["origin_port"] == "Santos"
        assert client.get("/brazil/water-port-pairs?origin_port=Unlisted").json()["count"] == 0
        assert client.get("/brazil/water-port-pairs?year=2026").status_code == 422
        assert client.get("/brazil/water-port-pairs?limit=501").status_code == 422
    with TestClient(create_app(water_dir=tmp_path)) as client:
        assert client.get("/brazil/water-port-pairs").status_code == 503
