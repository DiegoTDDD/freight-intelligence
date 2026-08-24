from pathlib import Path

import polars as pl


INPUT = Path("data/gold/faf5/top_corridors.parquet")
OUTPUT = Path("data/gold/faf5/corridor_summary.parquet")


def main() -> None:
    df = (
        pl.scan_parquet(INPUT)
        .group_by(["dms_orig", "dms_dest", "year"])
        .agg(
            pl.col("tons").sum().alias("total_tons")
        )
        .sort("total_tons", descending=True)
        .collect()
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(OUTPUT)

    print(f"Corridor analysis created: {OUTPUT}")
    print(f"Records: {df.height}")


if __name__ == "__main__":
    main()