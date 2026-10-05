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
        "corridor_summary.parquet",
        "corridor_concentration.parquet",
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


def test_silver_no_nulls_in_key_columns():
    key_columns = [
        "dms_orig",
        "dms_dest",
        "sctg2",
        "metric_type",
        "year",
    ]

    df = pl.scan_parquet(SILVER).select(key_columns).collect()

    for column in key_columns:
        assert df.get_column(column).null_count() == 0


def test_silver_metric_values_non_negative():
    df = pl.scan_parquet(SILVER).select("value").collect()

    assert df.get_column("value").min() >= 0


def test_gold_annual_kpis_quality():
    df = pl.read_parquet(GOLD / "annual_kpis.parquet")

    assert df.get_column("year").min() == 2017
    assert df.get_column("year").max() == 2050
    assert set(df.get_column("metric_type").unique()) == {
        "tons",
        "value",
        "tmiles",
    }
    assert df.get_column("total_value").min() >= 0
    assert df.get_column("avg_value").min() >= 0
    assert df.get_column("records").min() > 0


def test_gold_commodity_mix_quality():
    df = pl.read_parquet(GOLD / "commodity_mix.parquet")

    assert df.get_column("year").min() == 2017
    assert df.get_column("year").max() == 2050
    assert df.get_column("tons").min() >= 0
    assert df.get_column("share").min() >= 0
    assert df.get_column("share").max() <= 1


def test_gold_mode_mix_quality():
    df = pl.read_parquet(GOLD / "mode_mix.parquet")

    assert df.get_column("year").min() == 2017
    assert df.get_column("year").max() == 2050
    assert df.get_column("tons").min() >= 0
    assert df.get_column("share").min() >= 0
    assert df.get_column("share").max() <= 1


def test_gold_top_corridors_quality():
    df = pl.read_parquet(GOLD / "top_corridors.parquet")

    assert df.get_column("year").min() == 2017
    assert df.get_column("year").max() == 2050
    assert df.get_column("tons").min() >= 0


def test_gold_corridor_summary_quality():
    df = pl.read_parquet(GOLD / "corridor_summary.parquet")

    assert df.get_column("year").min() == 2017
    assert df.get_column("year").max() == 2050
    assert df.get_column("total_tons").min() >= 0
    assert df.get_column("share").min() >= 0
    assert df.get_column("share").max() <= 1
    assert df.get_column("rank").min() == 1


def test_gold_corridor_concentration_quality():
    df = pl.read_parquet(GOLD / "corridor_concentration.parquet")

    assert df.get_column("year").min() == 2017
    assert df.get_column("year").max() == 2050

    assert df.get_column("total_tons").min() >= 0
    assert df.get_column("top10_tons").min() >= 0
    assert df.get_column("top50_tons").min() >= 0
    assert df.get_column("top100_tons").min() >= 0

    assert df.get_column("top10_share").min() >= 0
    assert df.get_column("top10_share").max() <= 1

    assert df.get_column("top50_share").min() >= 0
    assert df.get_column("top50_share").max() <= 1

    assert df.get_column("top100_share").min() >= 0
    assert df.get_column("top100_share").max() <= 1