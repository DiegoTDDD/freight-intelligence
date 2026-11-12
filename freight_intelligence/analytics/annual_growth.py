import polars as pl

INPUT_PATH = "data/gold/faf5/annual_kpis.parquet"
OUTPUT_PATH = "data/gold/faf5/annual_growth.parquet"


def validate_totals(data):
    if data.is_empty() or not {"metric_type", "year", "total_value"}.issubset(data.columns):
        raise ValueError("Annual totals require nonempty metric_type, year and total_value")
    fields = data.select("metric_type", "year", "total_value")
    if any(fields.null_count().row(0)):
        raise ValueError("Annual totals contain nulls")
    if not data["year"].dtype.is_integer() or not data["total_value"].dtype.is_numeric():
        raise ValueError("Annual totals require integer years and numeric values")
    if not data["total_value"].is_finite().all() or (data["total_value"] < 0).any():
        raise ValueError("Annual totals must be finite and nonnegative")
    if data.select(pl.struct("metric_type", "year").is_duplicated().any()).item():
        raise ValueError("Duplicate annual metric/year pairs")


def main():
    source = pl.read_parquet(INPUT_PATH)
    validate_totals(source)
    df = (
        source
        .sort(["metric_type", "year"])
        .with_columns(
            pl.col("total_value")
            .shift(1)
            .over("metric_type")
            .alias("previous_total_value"),
            pl.col("year").shift(1).over("metric_type").alias("previous_year"),
        )
        .with_columns(
            (
                pl.col("total_value") - pl.col("previous_total_value")
            ).alias("absolute_change"),
            pl.when(pl.col("previous_total_value") > 0)
            .then((pl.col("total_value") / pl.col("previous_total_value")) - 1)
            .otherwise(None).alias("growth_rate"),
            (pl.col("year") - pl.col("previous_year")).alias("elapsed_years"),
        )
        .with_columns(
            pl.when((pl.col("previous_total_value") > 0) & (pl.col("elapsed_years") > 0))
            .then((pl.col("total_value") / pl.col("previous_total_value"))
                  ** (1 / pl.col("elapsed_years")) - 1)
            .otherwise(None).alias("annualized_growth_rate")
        )
    )

    df.write_parquet(OUTPUT_PATH)

    print(f"Annual growth analysis created: {OUTPUT_PATH}")
    print(f"Records: {df.height}")


if __name__ == "__main__":
    main()
