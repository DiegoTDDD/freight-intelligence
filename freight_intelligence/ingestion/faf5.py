from pathlib import Path

import polars as pl

from freight_intelligence.config.settings import FAF_RAW_DIR


CSV_PATH = FAF_RAW_DIR / "forecast" / "FAF5.5.1_HiLoForecasts.csv"
BRONZE_DIR = Path("data/bronze/faf5")


def ingest_faf5() -> Path:
    """Convert the official FAF5 CSV into partitioned Parquet."""

    BRONZE_DIR.mkdir(parents=True, exist_ok=True)

    output_path = BRONZE_DIR / "faf5_forecasts.parquet"

    (
        pl.scan_csv(
            CSV_PATH,
            infer_schema_length=10_000,
            null_values=["NULL", "null", ""],
        )
        .sink_parquet(
            output_path,
            compression="zstd",
        )
    )

    return output_path


if __name__ == "__main__":
    path = ingest_faf5()
    print(f"Bronze dataset created: {path}")