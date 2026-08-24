from pathlib import Path

import polars as pl


BRONZE = Path("data/bronze/faf5/faf5_forecasts.parquet")
SILVER = Path("data/silver/faf5/faf5_long.parquet")
GOLD = Path("data/gold/faf5")


def test_bronze_exists():
    assert BRONZE.exists()


def test_silver_exists():
    assert SILVER.exists()


def test_gold_datasets_exist():
    expected = [
        "annual_kpis.parquet",
        "commodity_mix.parquet",
        "mode_mix.parquet",
        "top_corridors.parquet",
    ]

    for filename in expected:
        assert (GOLD / filename).exists()


def test_bronze_row_count():
    rows = pl.scan_parquet(BRONZE).select(pl.len()).collect().item()
    assert rows == 2_503_352


def test_silver_row_count():
    rows = pl.scan_parquet(SILVER).select(pl.len()).collect().item()
    assert rows == 97_630_728


def test_silver_schema():
    schema = pl.scan_parquet(SILVER).collect_schema()

    expected_columns = {
        "fr_orig",
        "dms_orig",
        "dms_dest",
        "fr_dest",
        "fr_inmode",
        "dms_mode",
        "fr_outmode",
        "sctg2",
        "trade_type",
        "dist_band",
        "value",
        "metric_type",
        "year",
    }

    assert set(schema.names()) == expected_columns


def test_silver_years():
    years = (
        pl.scan_parquet(SILVER)
        .select("year")
        .unique()
        .collect()
        .get_column("year")
        .to_list()
    )

    assert min(years) == 2017
    assert max(years) == 2050


def test_silver_metric_types():
    metrics = (
        pl.scan_parquet(SILVER)
        .select("metric_type")
        .unique()
        .collect()
        .get_column("metric_type")
        .to_list()
    )

    assert set(metrics) == {"tons", "value", "tmiles"}