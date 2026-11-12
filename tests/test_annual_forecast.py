import json

import numpy as np
import polars as pl
import pytest

from freight_intelligence.ml.annual_forecast import build_forecast, main, predict


def annual(values=None, years=None):
    return pl.DataFrame(
        {
            "metric_type": ["tons"] * 6,
            "year": years if years is not None else [2017, 2018, 2020, 2025, 2030, 2050],
            "total_value": values
            if values is not None
            else [100.0, 110.0, 130.0, 180.0, 230.0, 430.0],
        }
    )


def test_linear_selection_uses_calendar_years_and_refits_all_input():
    forecast, evaluation = build_forecast(annual(), 2052, holdout_points=2)
    assert evaluation.filter(pl.col("selected"))["model"].to_list() == ["linear"]
    assert forecast["year"].to_list() == [2051, 2052]
    np.testing.assert_allclose(forecast["forecast_value"], [440, 450])
    assert evaluation["train_end_year"].to_list() == [2025] * 3
    assert evaluation["validation_start_year"].to_list() == [2030] * 3
    assert set(forecast["result_type"]) == {"faf_scenario_extrapolation"}


def test_validation_does_not_fit_on_held_out_values():
    _, original = build_forecast(annual(), 2052, holdout_points=2)
    altered = annual([100.0, 110.0, 130.0, 180.0, 1000.0, 1000.0])
    _, evaluation = build_forecast(altered, 2052, holdout_points=2)
    # With a fixed training prefix the linear predictions remain 230 and 430.
    linear = evaluation.filter(pl.col("model") == "linear")
    assert linear["mae"].item() == pytest.approx(670)
    assert original.filter(pl.col("model") == "linear")["mae"].item() < 1e-10


def test_cagr_uses_elapsed_years():
    result = predict(
        "cagr", np.array([2000.0, 2010.0]), np.array([100.0, 200.0]), np.array([2020.0])
    )
    assert result[0] == pytest.approx(400)


def test_zero_series_has_finite_results_and_no_undefined_cagr():
    forecast, evaluation = build_forecast(annual([0.0] * 6), 2051)
    assert forecast["forecast_value"].to_list() == [0.0]
    assert forecast["model"].to_list() == ["persistence"]
    assert "cagr" not in evaluation["model"]
    assert evaluation["wape"].null_count() == evaluation.height


def test_multiple_metrics_are_evaluated_independently():
    data = pl.concat(
        [annual(), annual([12.0] * 6).with_columns(pl.lit("value").alias("metric_type"))]
    )
    forecast, evaluation = build_forecast(data.reverse(), 2052, 2)
    assert forecast.height == 4
    assert evaluation.filter(pl.col("selected")).height == 2
    assert forecast.filter(pl.col("metric_type") == "value")["forecast_value"].to_list() == [
        12.0,
        12.0,
    ]


@pytest.mark.parametrize(
    "data, message",
    [
        (annual().head(3), "two training"),
        (pl.concat([annual(), annual().head(1)]), "duplicate"),
        (annual([100.0, 110.0, -1.0, 180.0, 230.0, 430.0]), "nonnegative"),
        (annual([100.0, 110.0, float("nan"), 180.0, 230.0, 430.0]), "finite"),
        (annual([100.0, 110.0, float("inf"), 180.0, 230.0, 430.0]), "finite"),
        (annual().with_columns(pl.lit(None).alias("total_value")), "null"),
        (annual().with_columns(pl.col("year").cast(pl.Float64)), "integers"),
        (annual().with_columns(pl.lit("other").alias("metric_type")), "Unsupported"),
        (annual().drop("year"), "requires nonempty"),
    ],
)
def test_invalid_input_is_rejected(data, message):
    with pytest.raises(ValueError, match=message):
        build_forecast(data, 2055)


@pytest.mark.parametrize("end_year, holdout", [(2050, 3), (2101, 3), (2055, 0)])
def test_invalid_parameters_are_rejected(end_year, holdout):
    with pytest.raises(ValueError):
        build_forecast(annual(), end_year, holdout)


def test_linear_predictions_are_nonnegative():
    prediction = predict(
        "linear", np.array([2000.0, 2010.0]), np.array([100.0, 10.0]), np.array([2030.0])
    )
    assert prediction.tolist() == [0.0]


def test_cli_outputs_provenance_and_preserves_input(tmp_path):
    source = tmp_path / "annual.parquet"
    output = tmp_path / "results"
    annual().write_parquet(source)
    before = source.read_bytes()
    main(["--input", str(source), "--output-dir", str(output), "--end-year", "2052"])
    assert source.read_bytes() == before
    assert pl.read_parquet(output / "forecast.parquet").height == 2
    assert (output / "evaluation.parquet").is_file()
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata["selection_metric"] == "mae"
    assert len(metadata["input_sha256"]) == 64
    assert "not accuracy against future observed" in metadata["interpretation"]


def test_cli_invalid_input_fails_without_creating_output(tmp_path):
    output = tmp_path / "results"
    with pytest.raises(SystemExit) as error:
        main(["--input", str(tmp_path / "missing.parquet"), "--output-dir", str(output)])
    assert error.value.code == 2
    assert not output.exists()
