import hashlib
import json
import shutil

import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_modes import DEFAULT_ROOT, MODES, load_modes


def test_five_modes_preserve_units_and_published_reference_values():
    data, metadata = load_modes()
    assert data.height == 132
    assert set(data["mode"]) == set(MODES)
    values = {row["indicator"]: (row["value"], row["unit"])
              for row in data.filter(data["year"] == 2024).to_dicts()}
    assert values["registered_trucks"] == (4.1, "million_vehicles")
    assert values["port_throughput"] == (1322.0, "million_tonnes")
    assert values["domestic_paid_cargo"] == (423.0, "million_kg")
    assert values["international_paid_cargo"] == (1012.8, "million_kg")
    assert values["natural_gas_daily_movement"] == (153.1, "million_m3_per_day")
    assert values["transpetro_oil_pipeline_movement"] == (79.3, "million_m3_at_20C")
    road = {row["indicator"]: (row["value"], row["unit"])
            for row in data.filter((data["mode"] == "road") & (data["year"] == 2025)).to_dicts()}
    assert road["mdfe_recorded_trips"] == (80.4, "million_trips")
    assert road["mdfe_transport_work"] == (749.4, "billion_tonne_km")
    assert "not a comparable modal split" in metadata["interpretation"]


def test_corrupted_snapshot_fails_closed(tmp_path):
    shutil.copytree(DEFAULT_ROOT, tmp_path / "modes")
    (tmp_path / "modes/indicators.csv").write_bytes(b"invalid")
    with pytest.raises(ValueError, match="integrity"):
        load_modes(tmp_path / "modes")


def test_mixed_indicator_units_rejected_even_with_updated_hash(tmp_path):
    shutil.copytree(DEFAULT_ROOT, tmp_path / "modes")
    file = tmp_path / "modes/indicators.csv"
    raw = file.read_bytes().replace(b"million_vehicles", b"tonnes", 1)
    file.write_bytes(raw)
    path = tmp_path / "modes/provenance.json"
    metadata = json.loads(path.read_bytes())
    metadata["files"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="Mixed units"):
        load_modes(tmp_path / "modes")


def test_public_modal_api_filters_and_missing_data(tmp_path):
    with TestClient(create_app()) as client:
        response = client.get("/brazil/indicators?mode=air&start_year=2024&end_year=2024")
        assert response.status_code == 200
        assert response.json()["count"] == 2
        assert {row["mode"] for row in response.json()["data"]} == {"air"}
        assert client.get("/brazil/indicators?mode=unavailable").status_code == 422
        assert client.get("/brazil/indicators?start_year=2025&end_year=2020").status_code == 422
    with TestClient(create_app(brazil_dir=tmp_path)) as client:
        assert client.get("/brazil/indicators").status_code == 503
