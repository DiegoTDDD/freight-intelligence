# Evaluation of historical observations

This independent command accepts a small annual CSV and a source manifest. It does not read
FAF scenario KPIs by default, run ingestion, replace forecasts, or promote a model.
A real historical dataset still needs to be supplied and checked by its provider.

CSV columns must be exactly `metric_type,year,total_value`. Supported metrics are `tons`,
`value`, and `tmiles`. Each metric/year pair must be unique, with integer years and finite,
nonnegative totals. Each metric needs enough points for training, validation and the final
test (at least eight with the defaults). Irregular years use calendar elapsed time;
one target point does not necessarily mean one year. Use consistent geography, coverage,
measurement methods and units across a series; the command cannot establish comparability.

The JSON manifest requires exactly `dataset_id`, `source`, `retrieved_at` (ISO date), `scope`,
`record_kind`, and `units` (a mapping for every metric). Use `historical_observations` only
for observed data; `synthetic_example` labels generated demonstrations. Projection inputs
are not accepted as a record kind. This declaration documents provenance, but cannot prove
that supplied values are observations. No network retrieval happens.

Run the included synthetic demonstration from the repository root:

```bash
python -m freight_intelligence.ml.historical_evaluation \
  --input docs/examples/historical_synthetic.csv \
  --manifest docs/examples/historical_synthetic_manifest.json \
  --output historical-example.zip
```

Choose a new output filename for every run: existing files are rejected. The output parent
must already exist. CSV input is limited to 2 MiB and the manifest to 64 KiB. The portable
ZIP contains the original CSV and manifest, metadata with their SHA-256 hashes, predictions,
and model scores. It remains separate from the API/dashboard scenario evaluation reports.

Persistence, linear and CAGR baselines use expanding training prefixes. Validation MAE
selects a model before the reserved final three points are evaluated. `--min-train-points`
and `--test-points` configure the split. The test uses a single origin without refitting or
selection using test values. The report retains all baseline scores and the selected model.
Synthetic demonstrations are explicitly labeled; they establish software behavior, not
forecasting accuracy on real freight. No guarantee of future accuracy follows from a
historical test either.

## Dashboard

Open the `Historical observations` workspace to upload a CSV or paste it, provide its
source manifest, and choose the training/test split. `Load synthetic historical example`
populates the pasted inputs; remove any selected upload to use that pasted example.
Only `Evaluate historical series` runs the evaluation. The last submitted result is
identified separately from pending edits. Failed submissions clear the previous result.
Results remain in session memory and can be downloaded without creating server-side files.
Evaluation is limited to 500 annual rows in total to bound interactive work.

## Optional forecasts from the supplied series

Add `--forecast-years 3` to the command to include three annual point estimates after the
last supplied year of each metric. The accepted range is 0–10; zero keeps the evaluation-only
bundle. The dashboard form also offers this option through `Forecast years after each series`.

The same validation-only selected models are retained. Reserved-test scores are computed
first; then each selected model is refit on all supplied observations for forecasting.
Test observations therefore contribute to the final fit, but never to model selection.
If a selected model fails during refitting or produces non-finite values, the report fails
instead of selecting a fallback using test results. Negative predictions are clipped to zero.

`forecast.csv` adds the future year, estimate, unit, selected model, last source year and
result kind (`supplied_historical_forecast` or `synthetic_example_forecast`). Its provenance
and refit policy are recorded in `metadata.json`. The bundle contains six files when this
option is enabled; it still does not replace FAF outputs or update the production API.
The estimates have no prediction intervals and do not guarantee future accuracy. Historical
status is a provider declaration, not independent verification of source quality.


A version-specific [FAF5.5.1 historical adapter](faf_historical.md) can prepare the local
2017–2021 subset without scanning the large raw/Silver files. Its manifest uses
`historical_estimates`; these are not direct measurements. Generic historical input also
accepts this record kind, and optional forecasts are labeled `historical_estimate_forecast`.
