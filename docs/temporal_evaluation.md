# Temporal baseline evaluation

```bash
python -m freight_intelligence.ml.temporal_evaluation
```

The command reads only `data/gold/faf5/annual_kpis.parquet` and writes a separate report to `artifacts/evaluation/annual/`. It does not rebuild FAF layers, replace forecasts, retrain a deployed model or change the dashboard's saved forecast selection.

## Split and selection

For each metric, sort unique years and reserve the final `--test-points` points (default 3). On the remaining prefix, start with `--min-train-points` points (default 4), predict the following `--horizon-points` available points (default 1), then expand training by one point and repeat. Predictions use elapsed calendar years rather than row positions.

Persistence, linear trend and CAGR are compared using MAE pooled across validation origin/target pairs. Only candidates available at every validation origin can be selected; incomplete candidates have null selection scores and explicit coverage counts. Exact ties follow persistence, linear, CAGR order. Overlapping validation windows are allowed when the horizon is greater than one point; each origin/target pair receives equal weight.

After selection is fixed, eligible baselines are fit once on the entire pre-test prefix and predict the reserved test window. There is no refitting within that window and test errors cannot change the selected model. Baseline test comparisons remain available in the report. A model that fails at the final test origin is reported as unavailable; it is not silently replaced using test performance.

The default validation predicts one next available point, while the reserved final test predicts three points from a single origin. These represent different lead times, so the two error levels should not be treated as identical-horizon estimates. `horizon_years` records each actual calendar gap. `--horizon-points 3` can be used to compare longer validation horizons when enough points exist.

## Files

| File | Contents |
| --- | --- |
| `predictions.parquet` | Phase, metric, model, origin/target year, calendar horizon, actual/predicted value, errors, selected flag |
| `scores.parquet` | Validation/test MAE, RMSE, WAPE, candidate eligibility and fold coverage |
| `metadata.json` | Input SHA-256, split parameters, selected models, interpretation and library versions |

WAPE is a fraction and is null when the actual total is zero. Successful runs replace files in the chosen report directory. Invalid inputs fail before output creation. Inputs must have unique metric/year pairs, finite nonnegative values, integer years and enough points for separate training, validation and test phases.

## FAF interpretation

The current input combines published FAF historical/scenario values through 2050. This evaluation measures reproduction of that published series, including projected points. The final test is temporally reserved for this experiment, but its targets are still FAF scenario values rather than future observed freight demand. Do not interpret its errors as operational forecast accuracy or as independent confirmation of FAF projections.

The default 39-row Gold table produces six validation origins per metric and reserves 2040, 2045 and 2050 for testing. This milestone adds the evaluation machinery; obtaining separately versioned historical observations remains necessary for operational forecasting claims.
