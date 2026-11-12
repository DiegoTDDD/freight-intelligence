"""Validate saved temporal reports for read-only API and dashboard consumers."""

import hashlib
import json
import math
from pathlib import Path

import polars as pl

from freight_intelligence.ml.annual_forecast import INTERPRETATION, MODELS

SCORE_COLUMNS = [
    "phase",
    "metric_type",
    "model",
    "eligible",
    "folds_expected",
    "folds_available",
    "prediction_count",
    "mae",
    "rmse",
    "wape",
    "selected",
]
PREDICTION_COLUMNS = [
    "phase",
    "metric_type",
    "model",
    "origin_year",
    "year",
    "horizon_years",
    "actual",
    "prediction",
    "absolute_error",
    "squared_error",
    "selected",
]


def load_temporal_report(directory: Path, source_file: Path):
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    if not isinstance(metadata, dict) or metadata.get("interpretation") != INTERPRETATION:
        raise ValueError("Invalid temporal report interpretation")
    source = source_file.read_bytes()
    if metadata.get("input_sha256") != hashlib.sha256(source).hexdigest():
        raise ValueError("Report does not match current annual indicators")
    if (
        metadata.get("selection_uses") != "validation_only"
        or metadata.get("selection_metric") != "mae"
    ):
        raise ValueError("Invalid selection policy")
    for key, minimum in [("min_train_points", 2), ("horizon_points", 1), ("test_points", 1)]:
        if type(metadata.get(key)) is not int or metadata[key] < minimum:
            raise ValueError("Invalid temporal split parameters")
    choices = metadata.get("selected_models")
    if (
        not isinstance(choices, dict)
        or not choices
        or not set(choices).issubset({"tons", "value", "tmiles"})
        or not set(choices.values()).issubset(MODELS)
    ):
        raise ValueError("Invalid selected models")
    scores = pl.read_parquet(directory / "scores.parquet").select(SCORE_COLUMNS)
    predictions = pl.read_parquet(directory / "predictions.parquet").select(PREDICTION_COLUMNS)
    if scores.is_empty() or predictions.is_empty():
        raise ValueError("Empty temporal report")
    for data, optional, numeric in [
        (scores, {"mae", "rmse", "wape"}, ["mae", "rmse", "wape"]),
        (predictions, set(), ["actual", "prediction", "absolute_error", "squared_error"]),
    ]:
        if any(
            data.select([name for name in data.columns if name not in optional]).null_count().row(0)
        ):
            raise ValueError("Null report fields")
        for column in numeric:
            values = data[column].drop_nulls()
            if len(values) and (
                not values.dtype.is_numeric() or not values.is_finite().all() or (values < 0).any()
            ):
                raise ValueError("Invalid numeric report values")
        if data["selected"].dtype != pl.Boolean or not set(data["phase"]).issubset(
            {"validation", "test"}
        ):
            raise ValueError("Invalid phase or selection flags")
        if not set(data["model"]).issubset(MODELS) or set(data["metric_type"]) != set(choices):
            raise ValueError("Invalid metric/model coverage")
    if scores["eligible"].dtype != pl.Boolean:
        raise ValueError("Invalid eligibility flags")
    for metric in choices:
        validation = scores.filter(
            (pl.col("metric_type") == metric) & (pl.col("phase") == "validation")
        )
        test = scores.filter((pl.col("metric_type") == metric) & (pl.col("phase") == "test"))
        if set(validation["model"]) != set(MODELS) or set(test["model"]) != set(
            validation.filter(pl.col("eligible"))["model"]
        ):
            raise ValueError("Incomplete baseline score coverage")
    for column in ["origin_year", "year", "horizon_years"]:
        if not predictions[column].dtype.is_integer():
            raise ValueError("Invalid report year types")
    if scores.select(pl.struct("phase", "metric_type", "model").is_duplicated().any()).item():
        raise ValueError("Duplicate score rows")
    if predictions.select(
        pl.struct("phase", "metric_type", "model", "origin_year", "year").is_duplicated().any()
    ).item():
        raise ValueError("Duplicate prediction rows")
    annual = pl.read_parquet(source)
    actual = {(row["metric_type"], row["year"]): row["total_value"] for row in annual.to_dicts()}
    cutoffs = {}
    for metric in choices:
        years = sorted(annual.filter(pl.col("metric_type") == metric)["year"].to_list())
        if (
            len(years)
            < metadata["test_points"] + metadata["min_train_points"] + metadata["horizon_points"]
        ):
            raise ValueError("Insufficient source coverage")
        cutoffs[metric] = years[-metadata["test_points"] - 1]
    for row in predictions.to_dicts():
        cutoff = cutoffs[row["metric_type"]]
        if (
            row["year"] <= row["origin_year"]
            or row["horizon_years"] != row["year"] - row["origin_year"]
        ):
            raise ValueError("Invalid prediction horizon")
        if row["phase"] == "validation" and row["year"] > cutoff:
            raise ValueError("Validation overlaps reserved test")
        if row["phase"] == "test" and (row["year"] <= cutoff or row["origin_year"] != cutoff):
            raise ValueError("Invalid final test origin")
        if not math.isclose(
            actual.get((row["metric_type"], row["year"]), math.nan), row["actual"], rel_tol=1e-9
        ):
            raise ValueError("Reference value differs from source")
        error = abs(row["prediction"] - row["actual"])
        if not math.isclose(
            error, row["absolute_error"], rel_tol=1e-7, abs_tol=1e-7
        ) or not math.isclose(error * error, row["squared_error"], rel_tol=1e-7, abs_tol=1e-7):
            raise ValueError("Inconsistent prediction errors")
        if row["selected"] != (row["model"] == choices[row["metric_type"]]):
            raise ValueError("Inconsistent prediction selection")
    for row in scores.to_dicts():
        rows = predictions.filter(
            (pl.col("metric_type") == row["metric_type"])
            & (pl.col("model") == row["model"])
            & (pl.col("phase") == row["phase"])
        )
        if (
            rows.height != row["prediction_count"]
            or rows["origin_year"].n_unique() != row["folds_available"]
        ):
            raise ValueError("Inconsistent report coverage")
        if row["selected"] != (row["model"] == choices[row["metric_type"]]):
            raise ValueError("Inconsistent score selection")
        if row["eligible"]:
            if rows.is_empty() or row["folds_expected"] != row["folds_available"]:
                raise ValueError("Incomplete eligible model")
            expected = {
                "mae": rows["absolute_error"].mean(),
                "rmse": math.sqrt(rows["squared_error"].mean()),
                "wape": rows["absolute_error"].sum() / rows["actual"].sum()
                if rows["actual"].sum()
                else None,
            }
            for name, value in expected.items():
                if (value is None) != (row[name] is None) or (
                    value is not None
                    and not math.isclose(value, row[name], rel_tol=1e-7, abs_tol=1e-7)
                ):
                    raise ValueError("Inconsistent aggregate errors")
        elif any(row[name] is not None for name in ("mae", "rmse", "wape")):
            raise ValueError("Incomplete model has selection scores")
    for metric, model in choices.items():
        rows = scores.filter(
            (pl.col("metric_type") == metric)
            & (pl.col("phase") == "validation")
            & pl.col("eligible")
        )
        if (
            rows.is_empty()
            or min(rows.to_dicts(), key=lambda row: (row["mae"], MODELS.index(row["model"])))[
                "model"
            ]
            != model
        ):
            raise ValueError("Selection is inconsistent with validation scores")
    public = {
        key: metadata[key]
        for key in (
            "interpretation",
            "input_sha256",
            "min_train_points",
            "horizon_points",
            "test_points",
            "selection_uses",
            "selection_metric",
            "selected_models",
        )
    }
    return public, scores, predictions
