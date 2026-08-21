from pathlib import Path

import polars as pl


BRONZE_PATH = Path("data/bronze/faf5/faf5_forecasts.parquet")
SILVER_DIR = Path("data/silver/faf5")

YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2025, 2030, 2035, 2040, 2045, 2050]


def build_silver() -> Path:
    SILVER_DIR.mkdir(parents=True, exist_ok=True)

    lf = pl.scan_parquet(BRONZE_PATH)

    dimensions = [
        "fr_orig",
        "dms_orig",
        "dms_dest",
        "fr_dest",
        "fr_inmode",
        "dms_mode",
        "fr_outmode",
        "sctg2",
        "trade_type",
        "dist_band",
    ]

    metric_columns = [
        f"tons_{year}" for year in YEARS
    ] + [
        f"value_{year}" for year in YEARS
    ] + [
        f"tmiles_{year}" for year in YEARS
    ]

    lf = (
        lf.select(dimensions + metric_columns)
        .unpivot(
            index=dimensions,
            on=metric_columns,
            variable_name="metric",
            value_name="value",
        )
        .with_columns(
            pl.col("metric")
            .str.extract(r"^(tons|value|tmiles)", 1)
            .alias("metric_type"),

            pl.col("metric")
            .str.extract(r"(\d{4})$", 1)
            .cast(pl.Int32)
            .alias("year"),
        )
        .drop("metric")
        .filter(pl.col("value").is_not_null())
        .sort(["year", "fr_orig", "fr_dest"])
    )

    output = SILVER_DIR / "faf5_long.parquet"

    lf.sink_parquet(
        output,
        compression="zstd",
    )

    return output


if __name__ == "__main__":
    path = build_silver()
    print(f"Silver dataset created: {path}")