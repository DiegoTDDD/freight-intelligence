import hashlib
import json
import shutil

import polars as pl
import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_water import DEFAULT_ROOT, load_water


def test_reviewed_water_records_keep_tonnes_teu_and_endpoints_distinct():
    data, metadata = load_water()
    assert data.height == 43
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
        assert client.get("/brazil/water-freight?dataset=inland_commodities&year=2024").json()["count"] == 0
    with TestClient(create_app(water_dir=tmp_path)) as client:
        assert client.get("/brazil/water-freight").status_code == 503
