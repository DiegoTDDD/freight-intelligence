import json
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from freight_intelligence.api.app import create_app
from freight_intelligence.evaluation_results import load_temporal_report
from freight_intelligence.ml.temporal_evaluation import main


@pytest.fixture
def report(tmp_path, monkeypatch):
    gold = tmp_path / "data/gold/faf5"
    gold.mkdir(parents=True)
    source = gold / "annual_kpis.parquet"
    pl.DataFrame(
        {
            "metric_type": ["tons"] * 8,
            "year": [2000, 2002, 2005, 2010, 2015, 2020, 2030, 2050],
            "total_value": [100.0, 102.0, 105.0, 110.0, 115.0, 120.0, 130.0, 150.0],
        }
    ).write_parquet(source)
    directory = tmp_path / "artifacts/evaluation/annual"
    main(
        [
            "--input",
            str(source),
            "--output-dir",
            str(directory),
            "--min-train-points",
            "3",
            "--test-points",
            "2",
        ]
    )
    monkeypatch.setenv("LOGINEXUS_DASHBOARD_DATA_ROOT", str(tmp_path))
    return tmp_path, directory, source


def test_report_reader_and_public_metadata(report):
    _, directory, source = report
    meta, scores, predictions = load_temporal_report(directory, source)
    assert meta["selected_models"] == {"tons": "linear"}
    assert scores.height == 6 and predictions.height == 15
    assert "input" not in meta


def test_api_filters_pagination_and_empty_results(report):
    _, directory, source = report
    with TestClient(create_app(gold_dir=source.parent, evaluation_dir=directory)) as client:
        body = client.get("/temporal-evaluation?phase=test&metric_type=tons").json()
        assert body["count"] == 3
        body = client.get(
            "/temporal-evaluation/predictions?phase=test&selected_only=true&limit=1&offset=1"
        ).json()
        assert body["total"] == 2 and body["count"] == 1
        assert body["data"][0]["year"] == 2050
        assert client.get("/temporal-evaluation?metric_type=value").json()["data"] == []
        assert client.get("/temporal-evaluation/predictions?offset=999").json()["data"] == []
        assert client.get("/temporal-evaluation?phase=invalid").status_code == 422
        assert client.get("/temporal-evaluation/predictions?limit=0").status_code == 422
        assert client.post("/temporal-evaluation", json={}).status_code == 405


@pytest.mark.parametrize("filename", ["metadata.json", "scores.parquet", "predictions.parquet"])
def test_missing_report_is_503_without_blocking_api(report, filename):
    _, directory, source = report
    (directory / filename).unlink()
    with TestClient(create_app(gold_dir=source.parent, evaluation_dir=directory)) as client:
        result = client.get("/temporal-evaluation")
        assert result.status_code == 503 and str(directory) not in result.text
        assert client.get("/annual-kpis").status_code == 200


@pytest.mark.parametrize(
    "column,value",
    [
        ("prediction", float("nan")),
        ("origin_year", 2099),
        ("actual", 0.0),
        ("absolute_error", 999.0),
        ("horizon_years", 999),
        ("selected", False),
    ],
)
def test_inconsistent_predictions_rejected(report, column, value):
    _, directory, source = report
    file = directory / "predictions.parquet"
    pl.read_parquet(file).with_columns(pl.lit(value).alias(column)).write_parquet(file)
    with pytest.raises(ValueError):
        load_temporal_report(directory, source)


def test_changed_source_and_score_mismatch_are_rejected(report):
    _, directory, source = report
    file = directory / "scores.parquet"
    pl.read_parquet(file).with_columns(pl.lit(999.0).alias("mae")).write_parquet(file)
    with pytest.raises(ValueError):
        load_temporal_report(directory, source)
    source.write_bytes(b"changed source")
    with pytest.raises(ValueError, match="current annual"):
        load_temporal_report(directory, source)


def test_missing_final_test_scores_rejected(report):
    _, directory, source = report
    file = directory / "scores.parquet"
    pl.read_parquet(file).filter(pl.col("phase") == "validation").write_parquet(file)
    with pytest.raises(ValueError, match="coverage"):
        load_temporal_report(directory, source)


def test_metadata_cannot_switch_selection_to_test(report):
    _, directory, source = report
    file = directory / "metadata.json"
    meta = json.loads(file.read_text())
    meta["selection_uses"] = "test"
    file.write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="policy"):
        load_temporal_report(directory, source)


def test_dashboard_temporal_view_and_phase_switch(report):
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "dashboards/app.py"), default_timeout=20
    ).run()
    app.selectbox(key="workspace").select("Temporal evaluation").run()
    assert not app.exception
    assert any(
        item.label == "Validation-selected baseline" and item.value == "LINEAR"
        for item in app.metric
    )
    assert app.dataframe[1].value["year"].tolist() == [2030, 2050]
    app.selectbox(key="temporal_phase").select("validation").run()
    assert not app.exception
    assert app.dataframe[1].value["year"].tolist() == [2010, 2015, 2020]


def test_dashboard_missing_report_has_friendly_state(report):
    _, directory, _ = report
    (directory / "metadata.json").unlink()
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "dashboards/app.py"), default_timeout=20
    ).run()
    app.selectbox(key="workspace").select("Temporal evaluation").run()
    assert not app.exception and app.warning
