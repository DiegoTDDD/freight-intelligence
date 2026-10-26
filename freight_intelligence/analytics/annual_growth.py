import polars as pl

INPUT_PATH = "data/gold/faf5/annual_kpis.parquet"
OUTPUT_PATH = "data/gold/faf5/annual_growth.parquet"


def main():
    df = (
        pl.read_parquet(INPUT_PATH)
        .sort(["metric_type", "year"])
        .with_columns(
            pl.col("total_value")
            .shift(1)
            .over("metric_type")
            .alias("previous_total_value")
        )
        .with_columns(
            (
                pl.col("total_value") - pl.col("previous_total_value")
            ).alias("absolute_change"),
            (
                (pl.col("total_value") / pl.col("previous_total_value")) - 1
            ).alias("growth_rate"),
        )
    )

    df.write_parquet(OUTPUT_PATH)

    print(f"Annual growth analysis created: {OUTPUT_PATH}")
    print(f"Records: {df.height}")


if __name__ == "__main__":
    main()
