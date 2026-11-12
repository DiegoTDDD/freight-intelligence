import json
from pathlib import Path

import polars as pl
import pytest
from streamlit.testing.v1 import AppTest

from freight_intelligence.ml.annual_forecast import main as forecast_main
from freight_intelligence.optimization.transport import main as transport_main

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dashboards/app.py"


@pytest.fixture
def dashboard_root(tmp_path, monkeypatch):
    gold = tmp_path / "data/gold/faf5"
    gold.mkdir(parents=True)
    pl.DataFrame(
        {
            "metric_type": ["tons"] * 5,
            "year": [2017, 2020, 2025, 2030, 2050],
            "total_value": [100.0, 120.0, 150.0, 180.0, 300.0],
        }
    ).write_parquet(gold / "annual_kpis.parquet")
    forecast_main(
        [
            "--input",
            str(gold / "annual_kpis.parquet"),
            "--output-dir",
            str(tmp_path / "models/faf5/annual"),
            "--end-year",
            "2052",
            "--holdout-points",
            "2",
        ]
    )
    transport_main(
        [
            "--scenario",
            str(ROOT / "docs/examples/transport_scenario.json"),
            "--output-dir",
            str(tmp_path / "artifacts/optimization/transport"),
        ]
    )
    monkeypatch.setenv("LOGINEXUS_DASHBOARD_DATA_ROOT", str(tmp_path))
    return tmp_path


def open_workspace(name):
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    app.selectbox(key="workspace").select(name).run()
    assert not app.exception
    return app


def test_missing_gold_does_not_block_optional_workspaces(dashboard_root):
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not app.exception
    assert any("Freight analytics are unavailable" in item.value for item in app.warning)
    app.selectbox(key="workspace").select("Transport plan").run()
    assert not app.exception
    assert any(
        item.label == "Total scenario cost" and item.value == "190.00" for item in app.metric
    )


def test_projection_chart_metrics_and_model_comparison(dashboard_root):
    app = open_workspace("Scenario extrapolations")
    assert any(item.label == "Extension through" and item.value == "2052" for item in app.metric)
    assert app.dataframe[0].value["Year"].tolist() == [2051, 2052]
    assert any("not accuracy against future observed" in item.value for item in app.info)
    assert len(app.dataframe[1].value) >= 2


def test_transport_filters_and_node_checks(dashboard_root):
    app = open_workspace("Transport plan")
    assert len(app.dataframe[0].value) == 3
    app.selectbox(key="transport_origin").select("supply-b").run()
    assert not app.exception
    assert app.dataframe[0].value["arc_id"].tolist() == ["b-y"]
    app.checkbox[0].uncheck().run()
    assert len(app.dataframe[0].value) == 2
    assert len(app.dataframe[1].value) == 4


def test_transport_empty_filter_has_clear_message(dashboard_root):
    app = open_workspace("Transport plan")
    app.selectbox(key="transport_origin").select("supply-b").run()
    app.selectbox(key="transport_destination").select("demand-x").run()
    assert not app.exception
    assert any("No links match" in item.value for item in app.info)


def test_missing_projection_has_friendly_state(dashboard_root):
    (dashboard_root / "models/faf5/annual/forecast.parquet").unlink()
    app = open_workspace("Scenario extrapolations")
    assert app.warning
    assert not app.metric


def test_projection_provenance_mismatch_is_rejected(dashboard_root):
    file = dashboard_root / "models/faf5/annual/metadata.json"
    metadata = json.loads(file.read_text())
    metadata["input_sha256"] = "0" * 64
    file.write_text(json.dumps(metadata))
    app = open_workspace("Scenario extrapolations")
    assert app.warning
    assert not app.dataframe


def test_changed_transport_file_invalidates_cache(dashboard_root):
    app = open_workspace("Transport plan")
    file = dashboard_root / "artifacts/optimization/transport/summary.json"
    metadata = json.loads(file.read_text())
    metadata["total_cost"] = 9999.0
    file.write_text(json.dumps(metadata))
    app.run()
    assert not app.exception
    assert app.warning
    assert not app.dataframe


@pytest.mark.parametrize(
    "column,value",
    [("forecast_value", float("nan")), ("year", 2051), ("model", 1), ("result_type", "observed")],
)
def test_invalid_projection_values_have_friendly_state(dashboard_root, column, value):
    file = dashboard_root / "models/faf5/annual/forecast.parquet"
    pl.read_parquet(file).with_columns(pl.lit(value).alias(column)).write_parquet(file)
    app = open_workspace("Scenario extrapolations")
    assert app.warning
    assert not app.dataframe


def test_historical_workspace_submission_and_failure_clear_result(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGINEXUS_DASHBOARD_DATA_ROOT", str(tmp_path))
    app = open_workspace("Historical observations")
    assert not app.dataframe
    app.button(key="historical_example").click().run()
    assert "synthetic" in app.text_area(key="historical_manifest").value
    submit = next(item for item in app.button if item.label == "Evaluate historical series")
    submit.click().run()
    assert not app.exception
    assert any("Synthetic example" in item.value for item in app.warning)
    assert len(app.dataframe[0].value) == 6
    assert app.session_state["historical_result"]
    app.text_area(key="historical_manifest").set_value('{"record_kind":"projection"}')
    next(item for item in app.button if item.label == "Evaluate historical series").click().run()
    assert not app.exception
    assert app.error
    assert not app.dataframe
    assert not (tmp_path / "artifacts").exists()


def test_historical_filters_keep_units_and_reserved_test_metrics_separate(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGINEXUS_DASHBOARD_DATA_ROOT", str(tmp_path))
    app = open_workspace("Historical observations")
    rows = ["metric_type,year,total_value"]
    for metric, factor in (("tons", 10), ("value", 1000)):
        rows.extend(f"{metric},{2000+i},{factor*(10+i)}" for i in range(10))
    manifest = {
        "dataset_id": "two-metrics", "source": "synthetic test", "retrieved_at": "2026-11-11",
        "scope": "test", "record_kind": "synthetic_example",
        "units": {"tons": "synthetic tons", "value": "synthetic dollars"},
    }
    app.text_area(key="historical_csv").set_value("\n".join(rows))
    app.text_area(key="historical_manifest").set_value(json.dumps(manifest))
    next(item for item in app.button if item.label == "Evaluate historical series").click().run()
    assert not app.exception
    assert set(app.dataframe[0].value["metric_type"]) == {"tons"}
    original = app.session_state["historical_result"]
    app.selectbox(key="historical_metric").select("value").run()
    app.selectbox(key="historical_phase").select("validation").run()
    app.selectbox(key="historical_model").select("persistence").run()
    assert not app.exception
    assert set(app.dataframe[0].value["metric_type"]) == {"value"}
    assert any("synthetic dollars" in item.value for item in app.caption)
    assert any(item.label == "Test MAE" for item in app.metric)
    assert app.session_state["historical_result"] == original


def test_historical_forecast_is_optional_and_download_bundle_matches_horizon(tmp_path, monkeypatch):
    import io
    from zipfile import ZipFile

    monkeypatch.setenv("LOGINEXUS_DASHBOARD_DATA_ROOT", str(tmp_path))
    app = open_workspace("Historical observations")
    app.button(key="historical_example").click().run()
    app.number_input(key="historical_forecast_years").set_value(3)
    next(item for item in app.button if item.label == "Evaluate historical series").click().run()
    assert not app.exception
    bundle = ZipFile(io.BytesIO(app.session_state["historical_result"]))
    forecast = pl.read_csv(bundle.read("forecast.csv"))
    assert forecast["year"].to_list() == [2010, 2011, 2012]
    assert forecast["forecast_value"].to_list() == pytest.approx([200, 210, 220])
    assert app.dataframe[-1].value["year"].tolist() == [2010, 2011, 2012]
    app.number_input(key="historical_forecast_years").set_value(0)
    next(item for item in app.button if item.label == "Evaluate historical series").click().run()
    assert not app.exception
    bundle = ZipFile(io.BytesIO(app.session_state["historical_result"]))
    assert "forecast.csv" not in bundle.namelist()
    assert not any(item.value == "Forecast after supplied history" for item in app.subheader)


def test_local_faf_historical_action_excludes_projection_years(tmp_path, monkeypatch):
    import io
    from zipfile import ZipFile

    monkeypatch.setenv("LOGINEXUS_DASHBOARD_DATA_ROOT", str(tmp_path))
    gold = tmp_path / "data/gold/faf5"
    gold.mkdir(parents=True)
    path = gold / "annual_kpis.parquet"
    pl.DataFrame([
        {"metric_type": metric, "year": year, "total_value": float(year - 1900)}
        for metric in ("tons", "value", "tmiles") for year in range(2017, 2026)
    ]).write_parquet(path)
    original = path.read_bytes()
    raw = tmp_path / "data/raw/faf5/forecast"
    raw.mkdir(parents=True)
    doc = raw / "bts_FAF_HiLoForecasts_README_20230929.txt"
    doc.write_text(
        "2023-09-29 FAF5.5 Annual estimates (Y + 1 through Y + 4) 2017 constant dollars"
    )
    app = open_workspace("Historical observations")
    app.button(key="historical_faf").click().run()
    assert not app.exception
    bundle = ZipFile(io.BytesIO(app.session_state["historical_result"]))
    history = pl.read_csv(bundle.read("observations.csv"))
    assert history.height == 15
    assert history["year"].max() == 2021
    assert "lineage.json" in bundle.namelist()
    assert any("too short" in item.value for item in app.warning)
    assert path.read_bytes() == original
    doc.unlink()
    app.button(key="historical_faf").click().run()
    assert not app.exception
    assert app.error
    assert not app.dataframe


def test_road_workspace_calculates_and_clears_failed_submission(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGINEXUS_DASHBOARD_DATA_ROOT", str(tmp_path))
    app = open_workspace("Supplied road route")
    payload = {
        "network": {"source": "synthetic UI test", "cost_unit": "test units",
                    "nodes": ["a", "b"], "edges": [{"id": "a-b", "origin": "a", "destination": "b",
                    "distance_km": 5.0, "toll": 2.0, "max_gross_weight_t": 40.0,
                    "max_height_m": 5.0, "closed": False}]},
        "vehicle": {"id": "test truck", "gross_weight_t": 20.0, "height_m": 4.0, "cost_per_km": 3.0},
        "origin": "a", "destination": "b",
    }
    app.text_area(key="road_request").set_value(json.dumps(payload))
    next(item for item in app.button if item.label == "Calculate supplied-network route").click().run()
    assert not app.exception
    assert app.session_state["road_result"]["total_cost"] == 17.0
    assert any(item.label == "Route distance (km)" and item.value == "5.00" for item in app.metric)
    payload["network"]["edges"][0]["closed"] = True
    app.text_area(key="road_request").set_value(json.dumps(payload))
    next(item for item in app.button if item.label == "Calculate supplied-network route").click().run()
    assert not app.exception
    assert app.error
    assert not app.metric
    assert not (tmp_path / "artifacts").exists()
