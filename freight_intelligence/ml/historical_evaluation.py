"""Evaluate explicitly identified annual historical observations from a small CSV."""

import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import polars as pl

from freight_intelligence.ml.annual_forecast import predict
from freight_intelligence.ml.temporal_evaluation import evaluate_temporally

MAX_INPUT_BYTES = 2 * 1024 * 1024


def historical_report(source, manifest_bytes, min_train_points=4, test_points=3, forecast_years=0):
    """Return a portable report; provenance is supplied, never inferred from values."""
    if len(source) > MAX_INPUT_BYTES or len(manifest_bytes) > 65536:
        raise ValueError("Historical input exceeds size limit")
    if type(forecast_years) is not int or not 0 <= forecast_years <= 10:
        raise ValueError("forecast_years must be an integer between 0 and 10")
    manifest = json.loads(manifest_bytes)
    required = {"dataset_id", "source", "retrieved_at", "scope", "record_kind", "units"}
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("Manifest requires dataset_id, source, retrieved_at, scope, record_kind, units")
    for key in ("dataset_id", "source", "retrieved_at", "scope"):
        if not isinstance(manifest[key], str) or not manifest[key].strip():
            raise ValueError(f"Manifest {key} must be nonempty text")
    from datetime import date

    date.fromisoformat(manifest["retrieved_at"])
    if manifest["record_kind"] not in (
        "historical_observations", "historical_estimates", "synthetic_example"
    ):
        raise ValueError("record_kind must identify observations or a synthetic example")
    data = pl.read_csv(source)
    if data.height > 500:
        raise ValueError("Historical evaluation is limited to 500 annual rows")
    if set(data.columns) != {"metric_type", "year", "total_value"}:
        raise ValueError("CSV requires exactly metric_type, year, total_value")
    units = manifest["units"]
    if not isinstance(units, dict) or set(units) != set(data["metric_type"]):
        raise ValueError("Manifest units must match every input metric")
    if any(not isinstance(unit, str) or not unit.strip() for unit in units.values()):
        raise ValueError("Every metric requires a nonempty unit")
    predictions, scores, choices = evaluate_temporally(
        data, min_train_points=min_train_points, test_points=test_points
    )
    interpretation = (
        "Synthetic example only; not evidence of accuracy on observed freight."
        if manifest["record_kind"] == "synthetic_example"
        else f"Evaluation against supplied {manifest['record_kind'].replace('_', ' ')}. "
        "Source classification is "
        "declared by the provider, not independently verified. No future accuracy guarantee."
    )
    metadata = {
        "interpretation": interpretation,
        "provenance": manifest,
        "input_sha256": hashlib.sha256(source).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "min_train_points": min_train_points,
        "test_points": test_points,
        "horizon_points": 1,
        "selection_uses": "validation_only",
        "selected_models": choices,
        "final_test": "single origin; no refitting or selection on test values",
        "intervals": "Calendar years; one point may span multiple years",
    }
    forecast = None
    if forecast_years:
        rows = []
        for metric, model in choices.items():
            series = data.filter(pl.col("metric_type") == metric).sort("year")
            years = series["year"].to_numpy().astype(float)
            values = series["total_value"].to_numpy().astype(float)
            target = np.arange(int(years[-1]) + 1, int(years[-1]) + forecast_years + 1)
            estimates = predict(model, years, values, target)
            for year, estimate in zip(target, estimates, strict=True):
                rows.append({
                    "metric_type": metric, "year": int(year), "forecast_value": float(estimate),
                    "unit": manifest["units"][metric], "model": model,
                    "source_end_year": int(years[-1]),
                    "result_type": (
                        "synthetic_example_forecast" if manifest["record_kind"] == "synthetic_example"
                        else "historical_estimate_forecast"
                        if manifest["record_kind"] == "historical_estimates"
                        else "supplied_historical_forecast"
                    ),
                })
        forecast = pl.DataFrame(rows)
        metadata["forecast"] = {
            "years_per_metric": forecast_years,
            "selection_uses": "same validation-only choices as evaluation",
            "refit": "selected models refit on all supplied points after reserved test scoring",
            "negative_predictions": "clipped to zero",
            "uncertainty": "point estimates only; no prediction intervals or accuracy guarantee",
            "refit_failure": "fail report; never select a fallback using reserved test results",
        }
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("observations.csv", source)
        archive.writestr("source_manifest.json", manifest_bytes)
        archive.writestr("metadata.json", json.dumps(metadata, indent=2, allow_nan=False))
        archive.writestr("predictions.csv", predictions.write_csv())
        archive.writestr("scores.csv", scores.write_csv())
        if forecast is not None:
            archive.writestr("forecast.csv", forecast.write_csv())
    return buffer.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-train-points", type=int, default=4)
    parser.add_argument("--test-points", type=int, default=3)
    parser.add_argument("--forecast-years", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        if args.input.stat().st_size > MAX_INPUT_BYTES or args.manifest.stat().st_size > 65536:
            raise ValueError("Historical input exceeds size limit")
        report = historical_report(
            args.input.read_bytes(), args.manifest.read_bytes(),
            args.min_train_points, args.test_points, args.forecast_years,
        )
        # Exclusive creation prevents replacing data or an earlier evaluation.
        with args.output.open("xb") as destination:
            destination.write(report)
    except (OSError, ValueError, pl.exceptions.PolarsError) as error:
        parser.exit(2, f"Historical evaluation failed: {error}\n")
    print("Historical evaluation bundle created; existing forecasts preserved.")


if __name__ == "__main__":
    main()
