import hashlib
import json
import shutil

import polars as pl
import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_water import DEFAULT_ROOT, load_water, load_water_pairs
from scripts.prepare_brazil_water_pairs import prepare as prepare_pairs


def test_reviewed_water_records_keep_tonnes_teu_and_endpoints_distinct():
    data, metadata = load_water()
    assert data.height == 55
    totals = {r["category"]: r["value"] for r in
              data.filter(pl.col("dataset") == "navigation_totals").to_dicts()}
    assert totals == {"Port throughput": 1403.1, "Coastal cabotage": 303.7, "Inland navigation": 91.3}
    states = data.filter(pl.col("dataset") == "coastal_state_endpoints")
    assert set(states["unit"]) == {"thousand_TEU"}
    sao_paulo = {r["direction"]: r["value"]
                 for r in states.filter(pl.col("category") == "SP").to_dicts()}
    assert sao_paulo == {"origin": 536.6, "destination": 538.9}
    assert states.filter(pl.col("category") == "RO").is_empty()  # Not a fabricated zero.
    assert any("no OD links" in note for note in metadata["quality_notes"])
    monthly = data.filter(pl.col("dataset") == "port_monthly")
    assert monthly.height == 12
    assert monthly["value"].sum() == 1402731832
    assert metadata["sources"][-1]["annual_headline_tonnes"] == 1402731833


@pytest.mark.parametrize("defect", ["corrupt", "wrong_unit", "wrong_year"])
def test_water_integrity_and_statistical_contracts(tmp_path, defect):
    root = tmp_path / "water"
    shutil.copytree(DEFAULT_ROOT, root)
    path = root / "water.csv"
    raw = path.read_bytes()
    if defect == "corrupt":
        path.write_bytes(b"invalid")
    else:
        if defect == "wrong_unit":
            raw = raw.replace(b"thousand_TEU", b"million_tonnes", 1)
        else:
            raw = raw.replace(b",2025,", b",2024,", 1)
        path.write_bytes(raw)
        metadata_path = root / "provenance.json"
        metadata = json.loads(metadata_path.read_bytes())
        metadata["files"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
        metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        load_water(root)


def test_water_api_filtering_and_missing_source(tmp_path):
    with TestClient(create_app()) as client:
        result = client.get("/brazil/water-freight?dataset=coastal_state_endpoints&direction=origin")
        assert result.status_code == 200
        assert result.json()["count"] == 11
        assert {row["direction"] for row in result.json()["data"]} == {"origin"}
        assert client.get("/brazil/water-freight?year=2026").status_code == 422
        assert client.get("/brazil/water-freight?dataset=unknown").status_code == 422
        monthly = client.get("/brazil/water-freight?dataset=port_monthly&year=2025").json()
        assert monthly["count"] == 12
        assert {row["unit"] for row in monthly["data"]} == {"tonnes"}
        assert client.get("/brazil/water-freight?dataset=inland_commodities&year=2024").json()["count"] == 0
    with TestClient(create_app(water_dir=tmp_path)) as client:
        assert client.get("/brazil/water-freight").status_code == 503


def test_regional_pairs_are_original_shares_and_rebuild_from_the_archived_export(tmp_path):
    data, metadata = load_water_pairs()
    assert data.height == 21 and metadata["unit"] == "share_fraction"
    assert data["share_of_cabotage"].sum() == pytest.approx(1, abs=1e-12)
    pair = data.filter((pl.col("origin_region") == "ZEE/Plat. Continental")
                       & (pl.col("destination_region") == "Sudeste"))
    assert pair["share_of_cabotage"].item() == pytest.approx(0.5121312507643868)
    assert not any("tonnes" in column for column in data.columns)
    assert "no year column" in metadata["period_evidence"]
    prepare_pairs(tmp_path)
    assert load_water_pairs(tmp_path)[0].equals(data)


def test_regional_pair_shares_reject_a_changed_total_even_with_updated_manifest(tmp_path):
    shutil.copytree(DEFAULT_ROOT, tmp_path / "water")
    root = tmp_path / "water"
    path = root / "coastal_region_pairs.csv"
    data = pl.read_csv(path).with_columns((pl.col("share_of_cabotage") * 0.5).alias("share_of_cabotage"))
    data.write_csv(path)
    manifest = root / "coastal_pairs_provenance.json"
    metadata = json.loads(manifest.read_bytes())
    metadata["files"][0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="reconcile"):
        load_water_pairs(root)


def test_regional_pair_api_preserves_the_full_denominator_under_filters(tmp_path):
    with TestClient(create_app()) as client:
        all_pairs = client.get("/brazil/water-pairs").json()
        assert all_pairs["count"] == 21
        selected = client.get("/brazil/water-pairs", params={
            "origin_region": "ZEE/Plat. Continental", "destination_region": "Sudeste"}).json()
        assert selected["count"] == 1
        assert selected["data"][0]["share_of_cabotage"] == pytest.approx(0.5121312507643868)
        assert client.get("/brazil/water-pairs?origin_region=Centro-Oeste").json()["count"] == 0
        assert client.get("/brazil/water-pairs?year=2024").status_code == 422
        assert client.get("/brazil/water-pairs?origin_region=SP").status_code == 422
    with TestClient(create_app(water_dir=tmp_path)) as client:
        assert client.get("/brazil/water-pairs").status_code == 503


def test_regional_pair_period_context_cannot_silently_change(tmp_path):
    shutil.copytree(DEFAULT_ROOT, tmp_path / "water")
    root = tmp_path / "water"
    path = root / "coastal_pairs_provenance.json"
    metadata = json.loads(path.read_bytes())
    metadata["filters"]["Carga.NRAno"] = [2026]
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="manifest"):
        load_water_pairs(root)
