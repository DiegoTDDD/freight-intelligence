import hashlib
import io
import json
import shutil
from zipfile import ZIP_DEFLATED, ZipFile

import polars as pl
import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_modal_forecasts import DEFAULT_ROOT, load_modal_forecasts


def test_reviewed_modal_reports_keep_units_vintage_and_all_candidates():
    report, metadata = load_modal_forecasts()
    assert report["observations"].height == 30
    assert metadata["source_end_year"] == 2024
    assert set(report["predictions"].filter(pl.col("phase") == "test")["year"]) == {2022, 2023, 2024}
    assert set(report["forecast"]["year"]) == {2025, 2026, 2027}
    selected = report["scores"].filter((pl.col("phase") == "test") & pl.col("selected"))
    values = {r["metric_type"]: r["wape"] for r in selected.to_dicts()}
    assert values["port_throughput"] == pytest.approx(0.02100052580821812)
    assert values["transpetro_oil_pipeline_movement"] == pytest.approx(0.16907345661358886)
    units = {r["metric_type"]: r["unit"] for r in report["forecast"].to_dicts()}
    assert units == {"port_throughput": "million_tonnes", "transpetro_oil_pipeline_movement": "million_m3_at_20C"}


@pytest.mark.parametrize("defect", ["wrong_actual", "wrong_unit", "leaked_test"])
def test_changed_report_contract_is_rejected_even_with_updated_archive_hash(tmp_path, defect):
    shutil.copytree(DEFAULT_ROOT, tmp_path / "report")
    root = tmp_path / "report"
    with ZipFile(root / "forecast.zip") as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    if defect in {"wrong_actual", "leaked_test"}:
        data = pl.read_csv(files["predictions.csv"])
        field = "actual" if defect == "wrong_actual" else "origin_year"
        data = data.with_columns((pl.col(field) + 1).alias(field))
        files["predictions.csv"] = data.write_csv().encode()
    else:
        data = pl.read_csv(files["forecast.csv"]).with_columns(pl.lit("kg").alias("unit"))
        files["forecast.csv"] = data.write_csv().encode()
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
    (root / "forecast.zip").write_bytes(output.getvalue())
    manifest = root / "provenance.json"
    metadata = json.loads(manifest.read_bytes())
    metadata["files"][0]["sha256"] = hashlib.sha256(output.getvalue()).hexdigest()
    manifest.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        load_modal_forecasts(root)


def test_modal_forecast_api_filters_dated_estimates_and_fails_closed(tmp_path):
    with TestClient(create_app()) as client:
        result = client.get("/brazil/modal-forecasts?mode=water&view=scores&phase=test").json()
        assert result["count"] == 3 and result["metadata"]["source_end_year"] == 2024
        assert {r["metric_type"] for r in result["data"]} == {"port_throughput"}
        result = client.get("/brazil/modal-forecasts?mode=pipeline&year=2025").json()
        assert result["count"] == 1 and result["data"][0]["source_end_year"] == 2024
        assert client.get("/brazil/modal-forecasts?view=forecast&phase=test").status_code == 422
        assert client.get("/brazil/modal-forecasts?view=scores&year=2024").status_code == 422
        assert client.get("/brazil/modal-forecasts?mode=road").status_code == 422
    with TestClient(create_app(modal_forecasts_dir=tmp_path)) as client:
        assert client.get("/brazil/modal-forecasts").status_code == 503
