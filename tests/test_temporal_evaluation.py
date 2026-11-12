import json

import polars as pl
import pytest

from freight_intelligence.ml.temporal_evaluation import evaluate_temporally, main


def annual(values=None):
    return pl.DataFrame(
        {
            "metric_type": ["tons"] * 8,
            "year": [2000, 2002, 2005, 2010, 2015, 2020, 2030, 2050],
            "total_value": values or [100.0, 102.0, 105.0, 110.0, 115.0, 120.0, 130.0, 150.0],
        }
    )


def test_linear_known_solution_and_disjoint_test():
    predictions, scores, selected = evaluate_temporally(annual(), 3, 1, 2)
    assert selected == {"tons": "linear"}
    validation = predictions.filter(pl.col("phase") == "validation")
    test = predictions.filter(pl.col("phase") == "test")
    assert validation["year"].max() == 2020
    assert test["year"].min() == 2030
    assert set(test["origin_year"]) == {2020}
    assert (predictions["origin_year"] < predictions["year"]).all()
    assert (
        scores.filter((pl.col("model") == "linear") & (pl.col("phase") == "test"))["mae"].item()
        < 1e-10
    )


def test_test_values_cannot_change_selection_or_predictions():
    original, _, selected = evaluate_temporally(annual(), 3, 1, 2)
    changed, _, choices = evaluate_temporally(
        annual([100.0, 102.0, 105.0, 110.0, 115.0, 120.0, 999.0, 999.0]), 3, 1, 2
    )
    assert selected == choices
    assert original["prediction"].to_list() == changed["prediction"].to_list()


def test_future_validation_values_do_not_change_earlier_predictions():
    original, _, _ = evaluate_temporally(annual(), 3, 1, 2)
    changed, _, _ = evaluate_temporally(
        annual([100.0, 102.0, 105.0, 110.0, 900.0, 120.0, 130.0, 150.0]), 3, 1, 2
    )
    assert (
        original.filter(pl.col("year") == 2010)["prediction"].to_list()
        == changed.filter(pl.col("year") == 2010)["prediction"].to_list()
    )


def test_calendar_horizons_and_overlapping_windows():
    predictions, _, _ = evaluate_temporally(annual(), 3, 2, 2)
    assert set(predictions.filter(pl.col("phase") == "test")["horizon_years"]) == {10, 30}
    validation = predictions.filter(
        (pl.col("phase") == "validation") & (pl.col("model") == "linear")
    )
    assert validation.filter(pl.col("year") == 2015).height == 2


def test_zero_series_excludes_incomplete_cagr_and_null_wape():
    _, scores, selected = evaluate_temporally(annual([0.0] * 8), 3, 1, 2)
    assert selected == {"tons": "persistence"}
    cagr = scores.filter(pl.col("model") == "cagr")
    assert not cagr["eligible"].any()
    assert cagr["mae"].null_count() == cagr.height
    assert scores["wape"].null_count() == scores.height


def test_partial_fold_coverage_cannot_win_selection():
    _, scores, _ = evaluate_temporally(
        annual([100.0, 102.0, 0.0, 110.0, 115.0, 120.0, 130.0, 150.0]), 3, 1, 2
    )
    cagr = scores.filter((pl.col("model") == "cagr") & (pl.col("phase") == "validation"))
    assert cagr["folds_available"].item() == 2
    assert cagr["folds_expected"].item() == 3
    assert not cagr["eligible"].item()
    assert not cagr["selected"].item()
    assert cagr["mae"].item() is None


def test_multiple_metrics_and_unsorted_rows():
    data = pl.concat(
        [annual(), annual().with_columns(pl.lit("value").alias("metric_type"))]
    ).reverse()
    _, _, choices = evaluate_temporally(data, 3, 1, 2)
    assert choices == {"tons": "linear", "value": "linear"}


@pytest.mark.parametrize(
    "train,horizon,test", [(1, 1, 2), (3, 0, 2), (3, 1, 0), (7, 1, 2), (True, 1, 2)]
)
def test_invalid_split_rejected(train, horizon, test):
    with pytest.raises(ValueError):
        evaluate_temporally(annual(), train, horizon, test)


@pytest.mark.parametrize(
    "column,value",
    [
        ("total_value", float("nan")),
        ("total_value", -1.0),
        ("metric_type", "unknown"),
        ("year", 2000),
    ],
)
def test_invalid_data_rejected(column, value):
    with pytest.raises(ValueError):
        evaluate_temporally(annual().with_columns(pl.lit(value).alias(column)), 3, 1, 2)


def test_cli_outputs_provenance_and_preserves_source(tmp_path):
    source = tmp_path / "annual.parquet"
    annual().write_parquet(source)
    original = source.read_bytes()
    output = tmp_path / "report"
    main(
        [
            "--input",
            str(source),
            "--output-dir",
            str(output),
            "--min-train-points",
            "3",
            "--test-points",
            "2",
        ]
    )
    assert source.read_bytes() == original
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata["selection_uses"] == "validation_only"
    assert len(metadata["input_sha256"]) == 64
    assert pl.read_parquet(output / "predictions.parquet").height > 0
    assert (output / "scores.parquet").exists()
