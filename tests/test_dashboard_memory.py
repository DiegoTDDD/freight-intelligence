import polars as pl

from freight_intelligence.dashboard_data import load_display_corridors


def test_corridor_reader_preserves_latest_ranking_without_full_session_copy(tmp_path):
    source = pl.DataFrame({
        "year": [2024] * 30 + [2050] * 30,
        "tons": list(range(100, 130)) + list(range(30)),
        "origin": list(range(60)),
    })
    path = tmp_path / "corridors.parquet"
    source.write_parquet(path)
    actual = load_display_corridors(path, 2050)
    expected = source.filter(pl.col("year") == 2050).sort("tons", descending=True).head(20)
    assert actual.equals(expected)
    assert actual.height == 20
