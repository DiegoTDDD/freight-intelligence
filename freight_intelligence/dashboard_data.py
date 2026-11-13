"""Small saved-result readers shared by the local dashboard and its tests."""

import hashlib
import json
from pathlib import Path

import polars as pl

from freight_intelligence.ml.annual_forecast import INTERPRETATION, MODELS


def file_signature(paths):
    """Include file versions in bounded dashboard cache keys."""
    return tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in paths)


def load_display_corridors(path, year):
    """Collect only the displayed ranking, before per-session cache copies.

    The source can contain nearly a million rows. Keep the same filter/sort/head
    semantics as the dashboard while allowing Parquet projection/predicate pushdown.
    """
    return (
        pl.scan_parquet(path).filter(pl.col("year") == year)
        .sort("tons", descending=True).head(20).collect()
    )


def load_projection_bundle(root: Path):
    return load_projection_files(
        root / "models/faf5/annual", root / "data/gold/faf5/annual_kpis.parquet"
    )


def load_projection_files(directory: Path, source_file: Path):
    """Validate provenance and baseline consistency for API and dashboard alike."""
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    if not isinstance(metadata, dict) or metadata.get("interpretation") != INTERPRETATION:
        raise ValueError("Unrecognized projection interpretation")
    source = source_file.read_bytes()
    if metadata.get("input_sha256") != hashlib.sha256(source).hexdigest():
        raise ValueError("Saved projections do not match the current annual indicators")
    annual = pl.read_parquet(source)
    forecast = pl.read_parquet(directory / "forecast.parquet")
    evaluation = pl.read_parquet(directory / "evaluation.parquet")
    contracts = [
        (annual, {"metric_type", "year", "total_value"}),
        (
            forecast,
            {"metric_type", "year", "forecast_value", "model", "source_end_year", "result_type"},
        ),
        (evaluation, {"metric_type", "model", "mae", "rmse", "wape", "selected"}),
    ]
    for data, columns in contracts:
        if data.is_empty() or not columns.issubset(data.columns):
            raise ValueError("Saved projection bundle has missing columns or rows")
        required = columns - {"wape"}
        if any(data.select(sorted(required)).null_count().row(0)):
            raise ValueError("Saved projection bundle contains null fields")
    for data, columns in [
        (annual, ["total_value"]),
        (forecast, ["forecast_value"]),
        (evaluation, ["mae", "rmse", "wape"]),
    ]:
        for column in columns:
            values = data[column].drop_nulls()
            if len(values) and (
                not values.dtype.is_numeric() or not values.is_finite().all() or (values < 0).any()
            ):
                raise ValueError("Saved projection bundle contains invalid values")
    if evaluation["selected"].dtype != pl.Boolean:
        raise ValueError("Invalid baseline selection flags")
    for data in (annual, forecast, evaluation):
        if data["metric_type"].dtype != pl.String or not set(data["metric_type"]).issubset(
            {"tons", "value", "tmiles"}
        ):
            raise ValueError("Invalid metric names")
    for data in (forecast, evaluation):
        if data["model"].dtype != pl.String or not set(data["model"]).issubset(MODELS):
            raise ValueError("Invalid baseline names")
    if not forecast["year"].dtype.is_integer() or not annual["year"].dtype.is_integer():
        raise ValueError("Invalid year values")
    if set(forecast["result_type"]) != {"faf_scenario_extrapolation"}:
        raise ValueError("Invalid projection result type")
    for metric in forecast["metric_type"].unique():
        selection = evaluation.filter((pl.col("metric_type") == metric) & pl.col("selected"))
        series = forecast.filter(pl.col("metric_type") == metric)
        source_series = annual.filter(pl.col("metric_type") == metric)
        if selection.height != 1 or source_series.is_empty():
            raise ValueError("Missing or ambiguous baseline selection")
        if set(series["model"]) != {selection["model"].item()}:
            raise ValueError("Projection model differs from selected baseline")
        if series["year"].min() <= source_series["year"].max():
            raise ValueError("Projection overlaps source scenario years")
        if series["year"].n_unique() != series.height:
            raise ValueError("Duplicate projection years")
    return annual, forecast, evaluation
