# Annual scenario baselines

The first modelling milestone operates on the 39-row annual Gold KPI table rather than the 97-million-row Silver layer. It is a standalone command and is not invoked by the main pipeline.

```bash
python -m freight_intelligence.ml.annual_forecast --end-year 2055
```

Defaults resolve relative to the installed project's root, so the command can run from another working directory. Explicit `--input` and `--output-dir` paths resolve from the caller's working directory. Each run replaces the three files in the chosen output directory. Invalid input is rejected before creating output files.

## Input contract

The input Parquet must contain `metric_type`, integer `year`, and numeric `total_value`. Supported metrics are `tons`, `value`, and `tmiles`; a subset is allowed. Each metric/year pair must be unique, values must be finite and nonnegative, and nulls are rejected. Rows may be unordered. At least two training points plus the requested number of holdout points are required per metric.

The default holdout contains the last three available points, not necessarily three consecutive years. `--holdout-points` changes that count. The requested end year must follow every metric's final input year and must be at most 2100. Predictions cover each calendar year after the final input point through the end year. Values retain the source table's metric units; no unit conversion is performed.

## Models and validation

1. Persistence repeats the final training value.
2. Linear trend fits least squares against elapsed calendar years.
3. CAGR annualizes the ratio between the first and final training values, then compounds from the final value. It requires positive endpoints.

The final holdout values never enter the validation fit. Every candidate predicts the entire holdout from the same training prefix. Evaluation reports MAE, RMSE and WAPE; WAPE is a fraction and is null when the holdout total is zero. MAE selects a model independently for each metric, with exact ties resolved in persistence, linear, CAGR order. The selected model is then refit on all input points to generate future values. Negative predictions are clipped to zero. Candidates with invalid endpoint values or non-finite predictions are excluded.

## Outputs

The default directory is `models/faf5/annual/`, excluded from Git:

| File | Contents |
| --- | --- |
| `forecast.parquet` | Metric, year, forecast value, selected model, source end year and explicit scenario result type |
| `evaluation.parquet` | One row per eligible metric/model candidate, errors, temporal split and selection flag |
| `metadata.json` | Interpretation, source path and SHA-256, parameters, model selection rules and library versions |

## Interpretation and next modelling milestone

FAF input includes forecast scenario values through 2050. Backtesting on those values measures how well simple trends reproduce that scenario. It is not a test against future observed freight demand. Model selection uses this holdout, so its reported error is not an independent final test score. No prediction intervals or causal claims are provided.

Before claiming predictive performance for freight demand, add a versioned source separating historical observations from projected scenarios, a temporal training/validation/test split, rolling-origin evaluation and comparisons against these baselines. More complex models should be added only after that evaluation design is in place.

Run the lightweight tests without source data:

```bash
python -m pytest tests --ignore=tests/test_faf5.py -q
```
