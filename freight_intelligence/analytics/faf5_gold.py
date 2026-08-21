from pathlib import Path

import polars as pl


SILVER_PATH = Path("data/silver/faf5/faf5_long.parquet")
GOLD_DIR = Path("data/gold/faf5")


def build_gold() -> None:
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    lf = pl.scan_parquet(SILVER_PATH)

    # =========================================================
    # 1. KPIs ANUAIS
    # =========================================================

    kpis = (
        lf.group_by(["year", "metric_type"])
        .agg(
            pl.col("value").sum().alias("total_value"),
            pl.col("value").mean().alias("avg_value"),
            pl.len().alias("records"),
        )
        .sort(["year", "metric_type"])
    )

    kpis.sink_parquet(
        GOLD_DIR / "annual_kpis.parquet",
        compression="zstd",
    )

    # =========================================================
    # 2. FLUXOS POR MODO
    # =========================================================

    by_mode = (
        lf.filter(pl.col("metric_type") == "tons")
        .group_by(["year", "fr_inmode"])
        .agg(
            pl.col("value").sum().alias("tons"),
        )
        .with_columns(
            (
                pl.col("tons")
                / pl.col("tons").sum().over("year")
            ).alias("share")
        )
        .sort(["year", "tons"], descending=[False, True])
    )

    by_mode.sink_parquet(
        GOLD_DIR / "mode_mix.parquet",
        compression="zstd",
    )

    # =========================================================
    # 3. PRINCIPAIS CORREDORES
    # =========================================================

    corridors = (
        lf.filter(pl.col("metric_type") == "tons")
        .group_by(
            [
                "year",
                "dms_orig",
                "dms_dest",
                "fr_inmode",
            ]
        )
        .agg(
            pl.col("value").sum().alias("tons"),
        )
        .sort(["year", "tons"], descending=[False, True])
    )

    corridors.sink_parquet(
        GOLD_DIR / "top_corridors.parquet",
        compression="zstd",
    )

    # =========================================================
    # 4. COMMODITIES
    # =========================================================

    commodities = (
        lf.filter(pl.col("metric_type") == "tons")
        .group_by(["year", "sctg2"])
        .agg(
            pl.col("value").sum().alias("tons"),
        )
        .with_columns(
            (
                pl.col("tons")
                / pl.col("tons").sum().over("year")
            ).alias("share")
        )
        .sort(["year", "tons"], descending=[False, True])
    )

    commodities.sink_parquet(
        GOLD_DIR / "commodity_mix.parquet",
        compression="zstd",
    )

    print("Gold layer created successfully.")


if __name__ == "__main__":
    build_gold()