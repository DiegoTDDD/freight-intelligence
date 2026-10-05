import polars as pl


INPUT_PATH = "data/gold/faf5/top_corridors.parquet"
OUTPUT_PATH = "data/gold/faf5/corridor_summary.parquet"
CONCENTRATION_OUTPUT_PATH = "data/gold/faf5/corridor_concentration.parquet"


def main():
    df = (
        pl.scan_parquet(INPUT_PATH)
        .filter(pl.col("dms_orig") != pl.col("dms_dest"))
        .group_by(
            [
                "dms_orig",
                "dms_dest",
                "year",
            ]
        )
        .agg(
            pl.col("tons").sum().alias("total_tons")
        )
        .with_columns(
            pl.col("total_tons")
            .sum()
            .over("year")
            .alias("year_total_tons")
        )
        .with_columns(
            (pl.col("total_tons") / pl.col("year_total_tons")).alias("share")
        )
        .with_columns(
            pl.col("total_tons")
            .rank(method="ordinal", descending=True)
            .over("year")
            .alias("rank")
        )
        .drop("year_total_tons")
        .sort(["year", "rank"])
        .collect()
    )

    df.write_parquet(OUTPUT_PATH)

    concentration = (
        df.group_by("year")
        .agg(
            pl.col("total_tons").sum().alias("total_tons"),
            pl.col("total_tons")
            .filter(pl.col("rank") <= 10)
            .sum()
            .alias("top10_tons"),
            pl.col("total_tons")
            .filter(pl.col("rank") <= 50)
            .sum()
            .alias("top50_tons"),
            pl.col("total_tons")
            .filter(pl.col("rank") <= 100)
            .sum()
            .alias("top100_tons"),
        )
        .with_columns(
            (pl.col("top10_tons") / pl.col("total_tons")).alias("top10_share"),
            (pl.col("top50_tons") / pl.col("total_tons")).alias("top50_share"),
            (pl.col("top100_tons") / pl.col("total_tons")).alias("top100_share"),
        )
        .sort("year")
    )

    concentration.write_parquet(CONCENTRATION_OUTPUT_PATH)

    print(f"Corridor analysis created: {OUTPUT_PATH}")
    print(f"Corridor concentration created: {CONCENTRATION_OUTPUT_PATH}")
    print(f"Records: {df.height}")


if __name__ == "__main__":
    main()