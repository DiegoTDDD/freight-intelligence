"""Small, reproducible baselines for extrapolating the FAF annual scenario."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import polars as pl

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS = ("persistence", "linear", "cagr")
INTERPRETATION = (
    "FAF5 scenario extrapolation. Validation measures agreement with held-out FAF "
    "scenario values, not accuracy against future observed freight demand."
)


def predict(model: str, years: np.ndarray, values: np.ndarray, target: np.ndarray):
    """Fit on the supplied training points, using elapsed calendar years."""
    if model == "persistence":
        result = np.full(len(target), values[-1], dtype=float)
    elif model == "linear":
        design = np.column_stack((years - years[0], np.ones(len(years))))
        slope, intercept = np.linalg.lstsq(design, values, rcond=None)[0]
        result = intercept + slope * (target - years[0])
    elif model == "cagr":
        if values[0] <= 0 or values[-1] <= 0:
            raise ValueError("CAGR requires positive endpoint values")
        rate = (np.log(values[-1]) - np.log(values[0])) / (years[-1] - years[0])
        with np.errstate(over="ignore", invalid="ignore"):
            result = np.exp(np.log(values[-1]) + rate * (target - years[-1]))
    else:
        raise ValueError(f"Unknown model: {model}")
    if not np.isfinite(result).all():
        raise ValueError(f"{model} produced non-finite predictions")
    return np.maximum(result, 0)


def build_forecast(data: pl.DataFrame, end_year: int, holdout_points: int = 3):
    """Select each metric's baseline by MAE on its final held-out points.

    The training prefix is never refit during validation. Only the selected model
    is refit on the full input before extrapolating to the requested end year.
    """
    required = {"metric_type", "year", "total_value"}
    if not required.issubset(data.columns) or data.is_empty():
        raise ValueError("Input requires nonempty metric_type, year and total_value columns")
    if not isinstance(holdout_points, int) or holdout_points < 1:
        raise ValueError("holdout_points must be a positive integer")
    if not isinstance(end_year, int) or not 1900 <= end_year <= 2100:
        raise ValueError("end_year must be an integer between 1900 and 2100")
    data = data.select(sorted(required))
    if any(data.null_count().row(0)):
        raise ValueError("Input contains null values")
    if data["metric_type"].dtype != pl.String:
        raise ValueError("metric_type must be a string")
    if not data["year"].dtype.is_integer():
        raise ValueError("year must contain integers")
    if not data["total_value"].dtype.is_numeric():
        raise ValueError("total_value must be numeric")
    if data.select(pl.struct("metric_type", "year").is_duplicated().any()).item():
        raise ValueError("Input contains duplicate metric/year pairs")
    if not set(data["metric_type"]).issubset({"tons", "value", "tmiles"}):
        raise ValueError("Unsupported metric_type")
    forecasts, evaluations = [], []
    for metric in sorted(data["metric_type"].unique()):
        series = data.filter(pl.col("metric_type") == metric).sort("year")
        years = series["year"].to_numpy().astype(float)
        values = series["total_value"].to_numpy().astype(float)
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError(f"{metric}: values must be finite and nonnegative")
        if len(years) < holdout_points + 2:
            raise ValueError(f"{metric}: need at least two training points plus the holdout")
        if years[0] < 1900 or end_year <= years[-1]:
            raise ValueError(f"{metric}: end_year must follow the last input year")
        train_years, test_years = years[:-holdout_points], years[-holdout_points:]
        train_values, test_values = values[:-holdout_points], values[-holdout_points:]
        target = np.arange(int(years[-1]) + 1, end_year + 1)
        candidates = []
        for model in MODELS:
            try:
                validation = predict(model, train_years, train_values, test_years)
                future = predict(model, years, values, target)
            except ValueError:
                # A zero endpoint or overflow can make CAGR unavailable.
                continue
            error = validation - test_values
            mae = float(np.mean(np.abs(error)))
            rmse = float(np.sqrt(np.mean(np.square(error))))
            denominator = float(np.sum(np.abs(test_values)))
            wape = float(np.sum(np.abs(error)) / denominator) if denominator else None
            if not np.isfinite([mae, rmse]).all():
                continue
            row = {
                "metric_type": metric,
                "model": model,
                "mae": mae,
                "rmse": rmse,
                "wape": wape,
                "train_end_year": int(train_years[-1]),
                "validation_start_year": int(test_years[0]),
                "validation_end_year": int(test_years[-1]),
                "validation_points": holdout_points,
            }
            candidates.append((row, future))
        if not candidates:
            raise ValueError(f"{metric}: no baseline produced finite results")
        winner, future = min(candidates, key=lambda candidate: candidate[0]["mae"])
        for row, _ in candidates:
            evaluations.append({**row, "selected": row is winner})
        for year, value in zip(target, future, strict=True):
            forecasts.append(
                {
                    "metric_type": metric,
                    "year": int(year),
                    "forecast_value": float(value),
                    "model": winner["model"],
                    "source_end_year": int(years[-1]),
                    "result_type": "faf_scenario_extrapolation",
                }
            )
    return pl.DataFrame(forecasts), pl.DataFrame(evaluations)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=PROJECT_ROOT / "data/gold/faf5/annual_kpis.parquet"
    )
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "models/faf5/annual")
    parser.add_argument("--end-year", type=int, default=2055)
    parser.add_argument("--holdout-points", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        # Read once so the recorded hash identifies exactly the evaluated input.
        source = args.input.read_bytes()
        forecast, evaluation = build_forecast(
            pl.read_parquet(source), args.end_year, args.holdout_points
        )
    except (OSError, ValueError, pl.exceptions.PolarsError) as error:
        parser.exit(2, f"Annual forecast failed: {error}\n")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    forecast.write_parquet(args.output_dir / "forecast.parquet")
    evaluation.write_parquet(args.output_dir / "evaluation.parquet")
    metadata = {
        "interpretation": INTERPRETATION,
        "input": str(args.input.resolve()),
        "input_sha256": hashlib.sha256(source).hexdigest(),
        "end_year": args.end_year,
        "holdout_points": args.holdout_points,
        "selection_metric": "mae",
        "tie_break_order": list(MODELS),
        "negative_predictions": "clipped to zero",
        "unavailable_models": "excluded when endpoints or numerical results are invalid",
        "numpy_version": np.__version__,
        "polars_version": pl.__version__,
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(INTERPRETATION)
    print(f"Created {forecast.height} scenario extrapolations.")


if __name__ == "__main__":
    main()
