import polars as pl

from freight_intelligence.analytics.annual_growth import validate_totals

INPUT_PATH = "data/gold/faf5/annual_kpis.parquet"
OUTPUT_PATH = "data/gold/faf5/annual_cagr.parquet"


def main():
    df = pl.read_parquet(INPUT_PATH)
    validate_totals(df)

    cagr = (
        df.group_by("metric_type")
        .agg(
            pl.col("year").min().alias("start_year"),
            pl.col("year").max().alias("end_year"),
            pl.col("total_value").sort_by("year").first().alias("start_value"),
            pl.col("total_value").sort_by("year").last().alias("end_value"),
        )
        .with_columns(
            pl.when((pl.col("start_value") > 0) & (pl.col("end_year") > pl.col("start_year")))
            .then(
                (pl.col("end_value") / pl.col("start_value"))
                ** (1 / (pl.col("end_year") - pl.col("start_year")))
                - 1
            ).otherwise(None).alias("cagr")
        )
        .sort("metric_type")
    )

    cagr.write_parquet(OUTPUT_PATH)

    print(f"Annual CAGR analysis created: {OUTPUT_PATH}")
    print(f"Records: {cagr.height}")


if __name__ == "__main__":
    main()
