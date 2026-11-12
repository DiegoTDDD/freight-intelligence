# Archived FAF5.5.1 historical estimate evaluation

The local archived README (`bts_FAF_HiLoForecasts_README_20230929.txt`) identifies the
2017 benchmark, annual estimates Y+1 through Y+4, and forecast years separately.
This preparation conservatively includes only 2017–2021 and excludes 2022 onward.
It uses the archived release's own units: thousand tons, million ton-miles, and
million constant 2017 dollars. See [BTS release information](https://www.bts.gov/faf/versions)
and the archived dataset DOI [10.21949/1529116](https://doi.org/10.21949/1529116).
Current FAF releases use different annual cutoffs; they must not be substituted into this
version-specific classification without reviewing their documentation.

```bash
python -m freight_intelligence.ml.faf_historical \
  --gold data/gold/faf5/annual_kpis.parquet \
  --documentation data/raw/faf5/forecast/bts_FAF_HiLoForecasts_README_20230929.txt \
  --prepared-at 2026-11-11 \
  --output faf-historical-2017-2021.zip
```

The command reads only the small, existing annual Gold and archived README. It does not
scan Bronze/Silver, reaggregate raw flows, run the pipeline, modify Gold, or create forecasts.
The destination must be a new filename in an existing directory. This is a version-specific
adapter, not a detector of arbitrary FAF releases. The filename and README do not independently
prove that the Gold was produced from this raw release; this remains a provenance limitation.

The seven-file bundle includes the usual evaluation files plus `lineage.json` with Gold and
README hashes, included/excluded years and limitations, and the original `source_readme.txt`.
Its manifest uses `historical_estimates`, distinguishing it from observed measurements and
synthetic examples. The manifest's date records preparation, not the original download date.
The original input CSV and manifest can be used in the dashboard's historical workspace.
Use minimum training points **2** and reserved test points **1** for this short series.

Training begins with 2017–2018, validation targets are 2019 and 2020, and the reserved
single-origin test targets 2021. The model is chosen only from validation. There are only
five points per metric; this is an exploratory check, not strong evidence of future accuracy.
All aggregates inherit the local Gold's coverage and upstream processing assumptions.

Local run on 2026-11-11 selected persistence for all three metrics. Reserved-test WAPE:

| Metric | Test year | WAPE |
| --- | --- | --- |
| Tons | 2021 | 2.25% |
| Value | 2021 | 2.38% |
| Ton-miles | 2021 | 1.68% |

These scores refer to this archived aggregate and one test year. They do not measure
performance on a newer release or on independently observed future freight demand.

## Open the local historical subset in the dashboard

In `Historical observations`, select `Evaluate local FAF historical estimates`.
The action evaluates the small existing Gold subset with the fixed short-series split
(two initial training points, two validation targets and the reserved year 2021).
The result shows its submitted split, source, units and limitations. The traceability
expander lists included/excluded years and source hashes. The download includes the
original archived README and lineage metadata. The form below is a separate custom-input
workflow; its pending fields do not change this submitted local evaluation.
Missing Gold/documentation produces a readable error and clears the previous result.
