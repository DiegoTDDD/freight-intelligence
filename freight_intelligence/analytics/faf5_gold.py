from pathlib import Path

import polars as pl

from freight_intelligence.utils.atomic_output import atomic_output

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

    with atomic_output(GOLD_DIR / "annual_kpis.parquet") as temporary:
        kpis.sink_parquet(temporary, compression="zstd")

    # =========================================================
    # 2. FLUXOS POR MODO
    # =========================================================

    by_mode = (
        lf.filter(pl.col("metric_type") == "tons")
        .group_by(["year", "dms_mode"])
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

    with atomic_output(GOLD_DIR / "mode_mix.parquet") as temporary:
        by_mode.sink_parquet(temporary, compression="zstd")

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
                "dms_mode",
            ]
        )
        .agg(
            pl.col("value").sum().alias("tons"),
        )
        .sort(["year", "tons"], descending=[False, True])
    )

    with atomic_output(GOLD_DIR / "top_corridors.parquet") as temporary:
        corridors.sink_parquet(temporary, compression="zstd")

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

    with atomic_output(GOLD_DIR / "commodity_mix.parquet") as temporary:
        commodities.sink_parquet(temporary, compression="zstd")

    print("Gold layer created successfully.")


if __name__ == "__main__":
    build_gold()