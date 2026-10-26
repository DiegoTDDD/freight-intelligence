import polars as pl

INPUT_PATH = "data/gold/faf5/commodity_mix.parquet"
LOOKUP_PATH = "data/gold/faf5/commodity_lookup.parquet"
OUTPUT_PATH = "data/gold/faf5/commodity_growth.parquet"


def main():
    df = pl.read_parquet(INPUT_PATH)
    lookup = pl.read_parquet(LOOKUP_PATH)

    growth = (
        df.group_by("sctg2")
        .agg(
            pl.col("year").min().alias("start_year"),
            pl.col("year").max().alias("end_year"),
            pl.col("tons").sort_by("year").first().alias("start_tons"),
            pl.col("tons").sort_by("year").last().alias("end_tons"),
        )
        .with_columns(
            (pl.col("end_tons") - pl.col("start_tons")).alias("absolute_change"),
            (
                (pl.col("end_tons") / pl.col("start_tons"))
                ** (1 / (pl.col("end_year") - pl.col("start_year")))
                - 1
            ).alias("cagr"),
        )
        .join(lookup, on="sctg2", how="left")
        .select(
            "sctg2",
            "commodity_name",
            "start_year",
            "end_year",
            "start_tons",
            "end_tons",
            "absolute_change",
            "cagr",
        )
        .sort("cagr", descending=True)
    )

    growth.write_parquet(OUTPUT_PATH)

    print(f"Commodity growth analysis created: {OUTPUT_PATH}")
    print(f"Records: {growth.height}")
    print(growth.head(10))


if __name__ == "__main__":
    main()
