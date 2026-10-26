import polars as pl

INPUT_PATH = "data/gold/faf5/commodity_mix.parquet"
LOOKUP_PATH = "data/gold/faf5/commodity_lookup.parquet"
OUTPUT_PATH = "data/gold/faf5/commodity_share_change.parquet"


def main():
    df = pl.read_parquet(INPUT_PATH)
    lookup = pl.read_parquet(LOOKUP_PATH)

    share_change = (
        df.group_by("sctg2")
        .agg(
            pl.col("year").min().alias("start_year"),
            pl.col("year").max().alias("end_year"),
            pl.col("share").sort_by("year").first().alias("start_share"),
            pl.col("share").sort_by("year").last().alias("end_share"),
        )
        .with_columns(
            (pl.col("end_share") - pl.col("start_share")).alias("share_change"),
        )
        .join(lookup, on="sctg2", how="left")
        .select(
            "sctg2",
            "commodity_name",
            "start_year",
            "end_year",
            "start_share",
            "end_share",
            "share_change",
        )
        .sort("share_change", descending=True)
    )

    share_change.write_parquet(OUTPUT_PATH)

    print(f"Commodity share change analysis created: {OUTPUT_PATH}")
    print(f"Records: {share_change.height}")
    print(share_change.head(10))


if __name__ == "__main__":
    main()
