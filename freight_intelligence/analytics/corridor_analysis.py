import polars as pl


INPUT_PATH = "data/gold/faf5/top_corridors.parquet"
OUTPUT_PATH = "data/gold/faf5/corridor_summary.parquet"


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
        .sort("total_tons", descending=True)
        .collect()
    )

    df.write_parquet(OUTPUT_PATH)

    print(f"Corridor analysis created: {OUTPUT_PATH}")
    print(f"Records: {df.height}")


if __name__ == "__main__":
    main()