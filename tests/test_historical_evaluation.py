import io
import json
from zipfile import ZipFile

import polars as pl
import pytest

from freight_intelligence.ml.historical_evaluation import historical_report, main


def inputs():
    source = pl.DataFrame({
        "metric_type": ["tons"] * 10,
        "year": list(range(2000, 2010)),
        "total_value": [100.0 + i * 10 for i in range(10)],
    }).write_csv().encode()
    manifest = {
        "dataset_id": "test", "source": "synthetic fixture", "retrieved_at": "2026-11-11",
        "scope": "test aggregate", "record_kind": "synthetic_example", "units": {"tons": "tons"},
    }
    return source, manifest


def report(source, manifest):
    return ZipFile(io.BytesIO(historical_report(source, json.dumps(manifest).encode())))


def test_bundle_preserves_inputs_and_marks_synthetic():
    source, manifest = inputs()
    bundle = report(source, manifest)
    assert bundle.read("observations.csv") == source
    metadata = json.loads(bundle.read("metadata.json"))
    assert "Synthetic example" in metadata["interpretation"]
    assert metadata["selection_uses"] == "validation_only"
    assert len(bundle.namelist()) == 5
    predictions = pl.read_csv(bundle.read("predictions.csv"))
    assert predictions.filter(pl.col("phase") == "test")["year"].min() == 2007


def test_reserved_test_changes_do_not_select_models():
    source, manifest = inputs()
    changed = pl.read_csv(source).with_columns(
        pl.when(pl.col("year") >= 2007).then(999999.0)
        .otherwise(pl.col("total_value")).alias("total_value")
    ).write_csv().encode()
    a = json.loads(report(source, manifest).read("metadata.json"))
    b = json.loads(report(changed, manifest).read("metadata.json"))
    assert a["selected_models"] == b["selected_models"]
    assert a["input_sha256"] != b["input_sha256"]


@pytest.mark.parametrize("field,value", [
    ("record_kind", "projection"), ("source", ""), ("units", {}),
    ("units", {"tons": ""}), ("retrieved_at", "yesterday"),
])
def test_invalid_provenance_rejected(field, value):
    source, manifest = inputs()
    manifest[field] = value
    with pytest.raises(ValueError):
        report(source, manifest)


def test_cli_refuses_existing_output(tmp_path):
    source, manifest = inputs()
    csv = tmp_path / "observations.csv"
    meta = tmp_path / "manifest.json"
    output = tmp_path / "report.zip"
    csv.write_bytes(source)
    meta.write_text(json.dumps(manifest))
    args = ["--input", str(csv), "--manifest", str(meta), "--output", str(output)]
    main(args)
    original = output.read_bytes()
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    assert output.read_bytes() == original

@pytest.mark.parametrize("kind", [[], {}, None])
def test_nontext_record_kind_rejected(kind):
    source, manifest = inputs()
    manifest["record_kind"] = kind
    with pytest.raises(ValueError):
        report(source, manifest)


def test_large_series_rejected_before_expanding_evaluation():
    source, manifest = inputs()
    oversized = pl.concat([pl.read_csv(source)] * 51).write_csv().encode()
    with pytest.raises(ValueError, match="500 annual rows"):
        report(oversized, manifest)


def test_forecast_reuses_validation_choice_and_refits_all_points():
    source, manifest = inputs()
    result = historical_report(source, json.dumps(manifest).encode(), forecast_years=3)
    bundle = ZipFile(io.BytesIO(result))
    forecast = pl.read_csv(bundle.read("forecast.csv"))
    metadata = json.loads(bundle.read("metadata.json"))
    assert forecast["year"].to_list() == [2010, 2011, 2012]
    assert forecast["forecast_value"].to_list() == pytest.approx([200, 210, 220])
    assert forecast["model"].unique().to_list() == [metadata["selected_models"]["tons"]]
    assert forecast["result_type"].unique().to_list() == ["synthetic_example_forecast"]
    assert forecast["source_end_year"].unique().to_list() == [2009]
    assert "all supplied points" in metadata["forecast"]["refit"]
    assert len(bundle.namelist()) == 6


@pytest.mark.parametrize("years", [-1, 11, True, 1.5])
def test_forecast_horizon_is_bounded(years):
    source, manifest = inputs()
    with pytest.raises(ValueError, match="forecast_years"):
        historical_report(source, json.dumps(manifest).encode(), forecast_years=years)


def test_observed_forecast_is_distinct_from_faf_projection():
    source, manifest = inputs()
    manifest["record_kind"] = "historical_observations"
    bundle = ZipFile(io.BytesIO(historical_report(
        source, json.dumps(manifest).encode(), forecast_years=1
    )))
    forecast = pl.read_csv(bundle.read("forecast.csv"))
    assert forecast["result_type"].item() == "supplied_historical_forecast"
    assert forecast["unit"].item() == "tons"
