# Freight Intelligence

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
├── commodity_mix.parquet
├── mode_mix.parquet
└── top_corridors.parquet
```

These datasets support freight-flow analysis, forecasting, visualization and optimization.

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
- [x] Automated tests
- [x] Git repository
- [x] GitHub integration

### Next Steps

- [ ] Data quality tests
- [ ] Freight corridor analytics
- [ ] Interactive dashboard
- [ ] Forecasting models
- [ ] Route optimization
- [ ] API layer
- [ ] Dockerization
- [ ] CI/CD
