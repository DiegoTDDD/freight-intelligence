# Freight Intelligence

![CI Pipeline](https://github.com/DiegoTDDD/freight-intelligence/actions/workflows/ci_pipeline.yml/badge.svg)

End-to-end freight intelligence platform for analyzing and forecasting freight flows using large-scale transportation data.

## Architecture

The project follows a Medallion Architecture:

```text
FAF5 Dataset
     │
     ▼
  INGESTION
     │
     ▼
   BRONZE
Raw structured data in Parquet
     │
     ▼
   SILVER
Long-format analytical dataset
     │
     ▼
    GOLD
Business-ready analytical datasets
     │
     ├── Annual KPIs
     ├── Commodity Mix
     ├── Mode Mix
     └── Top Freight Corridors
     │
     ▼
Analytics / ML / Optimization
```

## Data Source

The project uses the Freight Analysis Framework (FAF5) developed by the U.S. Bureau of Transportation Statistics (BTS) and Oak Ridge National Laboratory (ORNL).

The current pipeline processes the FAF5.5.1 high/low freight forecast dataset.

## Technology Stack

- Python 3.13
- Polars
- Pandas
- PyArrow
- DuckDB
- NumPy
- Scikit-learn
- Plotly
- Pytest

## Pipeline

### Bronze

The ingestion layer converts the original FAF5 CSV dataset into Parquet.

```text
data/raw/faf5/
        ↓
data/bronze/faf5/faf5_forecasts.parquet
```

Dataset:

- 2,503,352 records
- 82 columns

### Silver

The transformation layer converts the wide FAF5 dataset into a long analytical format.

```text
data/bronze/faf5/
        ↓
data/silver/faf5/faf5_long.parquet
```

Dataset:

- 97,630,728 records
- 13 columns

Main analytical dimensions include:

- Origin
- Destination
- Freight mode
- Commodity
- Trade type
- Distance band
- Year
- Metric type

### Gold

The analytics layer produces business-ready datasets:

```text
data/gold/faf5/

├── annual_kpis.parquet
├── annual_growth.parquet
├── annual_cagr.parquet
├── commodity_mix.parquet
├── commodity_lookup.parquet
├── commodity_growth.parquet
├── commodity_share_change.parquet
├── mode_mix.parquet
├── top_corridors.parquet
├── corridor_summary.parquet
└── corridor_concentration.parquet
```

These datasets support freight-flow analysis, forecasting, visualization and optimization.

## Running the Pipeline

Place the FAF5.5.1 source files in the data/raw/faf5/forecast/ directory:

- FAF5.5.1_HiLoForecasts.csv
- FAF5_metadata.xlsx

The pipeline reuses existing Bronze and Silver Parquet files. Use fresh source data only after removing or updating the corresponding generated outputs. The `--skip-existing` option skips a step only when all of its expected output files exist; it does not check whether those files are up to date.

Run the complete pipeline from the project root:

    python -m freight_intelligence.pipeline

Launch the dashboard after generating the datasets:

    streamlit run dashboards/app.py

Install application dependencies with:

    python -m pip install -e ".[app]"

## Continuous Integration

GitHub Actions runs the configuration tests (`tests/test_config.py`) on every push and pull request. `tests/test_faf5.py` validates the full FAF5 dataset (~100M rows), which is generated locally and is not stored in the repository, so it only runs where that data exists.

## Data Engineering Principles

The project is designed around:

- Columnar storage with Parquet
- Lazy execution with Polars
- Streaming processing for large datasets
- Medallion architecture
- Separation between raw, transformed and analytical data
- Reproducible pipelines
- Automated testing
- Git-based version control

## Project Structure

```text
freight-intelligence/
│
├── freight_intelligence/
│   ├── analytics/
│   ├── config/
│   ├── ingestion/
│   ├── ml/
│   ├── optimization/
│   ├── transformations/
│   └── utils/
│
├── data/
│   ├── raw/
│   ├── bronze/
│   ├── silver/
│   └── gold/
│
├── dashboards/
├── docs/
├── notebooks/
├── scripts/
├── tests/
│
├── pyproject.toml
└── README.md
```

## Current Status

### Completed

- [x] Project structure
- [x] Python package configuration
- [x] Environment setup
- [x] FAF5 dataset ingestion
- [x] Bronze layer
- [x] Silver transformation
- [x] Gold analytical layer
- [x] Data quality tests
- [x] Freight corridor analytics
- [x] Interactive dashboard
- [x] Automated tests
- [x] Git repository
- [x] GitHub integration
- [x] Continuous integration (GitHub Actions)

### Next Steps

- [ ] Forecasting models
- [ ] Route optimization
- [ ] API layer
- [ ] Dockerization
- [ ] Continuous deployment (CD)
