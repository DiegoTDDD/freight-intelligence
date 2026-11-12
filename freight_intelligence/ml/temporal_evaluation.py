"""Expanding-window baseline comparison with a final reserved test window."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import polars as pl

from freight_intelligence.ml.annual_forecast import INTERPRETATION, MODELS, PROJECT_ROOT, predict


def errors(actual, predicted):
    with np.errstate(over="ignore", invalid="ignore"):
        absolute = np.abs(predicted - actual)
        squared = np.square(predicted - actual)
    if not np.isfinite(absolute).all() or not np.isfinite(squared).all():
        raise ValueError("Non-finite evaluation errors")
    return absolute, squared


def evaluate_temporally(data, min_train_points=4, horizon_points=1, test_points=3):
    for name, value, minimum in (
        ("min_train_points", min_train_points, 2),
        ("horizon_points", horizon_points, 1),
        ("test_points", test_points, 1),
    ):
        if type(value) is not int or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    required = {"metric_type", "year", "total_value"}
    if data.is_empty() or not required.issubset(data.columns):
        raise ValueError("Input requires nonempty metric_type, year and total_value columns")
    data = data.select(sorted(required))
    if any(data.null_count().row(0)):
        raise ValueError("Input contains null values")
    if data["metric_type"].dtype != pl.String or not set(data["metric_type"]).issubset(
        {"tons", "value", "tmiles", "tonne_km"}
    ):
        raise ValueError("Unsupported metric_type")
    if not data["year"].dtype.is_integer() or not data["total_value"].dtype.is_numeric():
        raise ValueError("Input requires integer years and numeric values")
    if data.select(pl.struct("metric_type", "year").is_duplicated().any()).item():
        raise ValueError("Duplicate metric/year pairs")
    values = data["total_value"]
    if not values.is_finite().all() or (values < 0).any() or data["year"].min() < 1900:
        raise ValueError("Values must be finite/nonnegative and years >= 1900")

    predictions, scores, choices = [], [], {}
    for metric in sorted(data["metric_type"].unique()):
        series = data.filter(pl.col("metric_type") == metric).sort("year")
        years = series["year"].to_numpy().astype(float)
        values = series["total_value"].to_numpy().astype(float)
        split = len(years) - test_points
        origins = list(range(min_train_points, split - horizon_points + 1))
        if not origins:
            raise ValueError(
                f"{metric}: insufficient points for training, validation and reserved test"
            )
        metric_scores, metric_predictions = [], []
        for model in MODELS:
            validation_rows, successful = [], 0
            for origin in origins:
                target = years[origin : origin + horizon_points]
                actual = values[origin : origin + horizon_points]
                try:
                    predicted = predict(model, years[:origin], values[:origin], target)
                    absolute, squared = errors(actual, predicted)
                except ValueError:
                    continue
                successful += 1
                for year, observed, estimate, ae, se in zip(
                    target, actual, predicted, absolute, squared, strict=True
                ):
                    validation_rows.append(
                        {
                            "phase": "validation",
                            "metric_type": metric,
                            "model": model,
                            "origin_year": int(years[origin - 1]),
                            "year": int(year),
                            "horizon_years": int(year - years[origin - 1]),
                            "actual": float(observed),
                            "prediction": float(estimate),
                            "absolute_error": float(ae),
                            "squared_error": float(se),
                        }
                    )
            eligible = successful == len(origins)
            metric_predictions.extend(validation_rows)
            metric_scores.append(
                score_rows(
                    validation_rows, metric, model, "validation", eligible, len(origins), successful
                )
            )
        candidates = [row for row in metric_scores if row["eligible"]]
        if not candidates:
            raise ValueError(f"{metric}: no baseline has complete validation coverage")
        # Only validation errors choose the baseline. Test values are untouched so far.
        winner = min(candidates, key=lambda row: row["mae"])["model"]
        choices[metric] = winner
        for candidate in candidates:
            model, rows = candidate["model"], []
            try:
                predicted = predict(model, years[:split], values[:split], years[split:])
                absolute, squared = errors(values[split:], predicted)
                for year, observed, estimate, ae, se in zip(
                    years[split:], values[split:], predicted, absolute, squared, strict=True
                ):
                    rows.append(
                        {
                            "phase": "test",
                            "metric_type": metric,
                            "model": model,
                            "origin_year": int(years[split - 1]),
                            "year": int(year),
                            "horizon_years": int(year - years[split - 1]),
                            "actual": float(observed),
                            "prediction": float(estimate),
                            "absolute_error": float(ae),
                            "squared_error": float(se),
                        }
                    )
            except ValueError:
                pass
            metric_predictions.extend(rows)
            metric_scores.append(
                score_rows(rows, metric, model, "test", bool(rows), 1, int(bool(rows)))
            )
        predictions.extend(
            {**row, "selected": row["model"] == winner} for row in metric_predictions
        )
        scores.extend({**row, "selected": row["model"] == winner} for row in metric_scores)
    return pl.DataFrame(predictions), pl.DataFrame(scores), choices


def score_rows(rows, metric, model, phase, eligible, expected, successful):
    actual = np.array([row["actual"] for row in rows])
    absolute = np.array([row["absolute_error"] for row in rows])
    squared = np.array([row["squared_error"] for row in rows])
    denominator = float(actual.sum()) if len(rows) else 0.0
    return {
        "phase": phase,
        "metric_type": metric,
        "model": model,
        "eligible": eligible,
        "folds_expected": expected,
        "folds_available": successful,
        "prediction_count": len(rows),
        "mae": float(absolute.mean()) if eligible else None,
        "rmse": float(np.sqrt(squared.mean())) if eligible else None,
        "wape": float(absolute.sum() / denominator) if eligible and denominator else None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=PROJECT_ROOT / "data/gold/faf5/annual_kpis.parquet"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "artifacts/evaluation/annual"
    )
    parser.add_argument("--min-train-points", type=int, default=4)
    parser.add_argument("--horizon-points", type=int, default=1)
    parser.add_argument("--test-points", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        source = args.input.read_bytes()
        predictions, scores, choices = evaluate_temporally(
            pl.read_parquet(source), args.min_train_points, args.horizon_points, args.test_points
        )
    except (OSError, ValueError, pl.exceptions.PolarsError) as error:
        parser.exit(2, f"Temporal evaluation failed: {error}\n")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    predictions.write_parquet(args.output_dir / "predictions.parquet")
    scores.write_parquet(args.output_dir / "scores.parquet")
    metadata = {
        "interpretation": INTERPRETATION,
        "input_sha256": hashlib.sha256(source).hexdigest(),
        "min_train_points": args.min_train_points,
        "horizon_points": args.horizon_points,
        "test_points": args.test_points,
        "selection_uses": "validation_only",
        "selection_metric": "mae",
        "selected_models": choices,
        "incomplete_validation": "excluded from model selection",
        "final_test": "single origin; no refitting or selection on test values",
        "overlapping_windows": "each origin/target pair has equal weight",
        "current_forecast_outputs": "preserved; report does not promote models automatically",
        "numpy_version": np.__version__,
        "polars_version": pl.__version__,
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(INTERPRETATION)
    print(
        f"Evaluated {predictions.height} origin/target predictions; reserved final test preserved."
    )
    print("Selected baselines:", json.dumps(choices, sort_keys=True))


if __name__ == "__main__":
    main()
