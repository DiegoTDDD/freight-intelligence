import polars as pl

from freight_intelligence.analytics import faf5_gold


def test_mode_mix_and_corridors_use_domestic_mode_not_foreign_entry_mode(tmp_path, monkeypatch):
    silver = tmp_path / "silver.parquet"
    gold = tmp_path / "gold"
    gold.mkdir()
    pl.DataFrame({"year": [2025, 2025], "metric_type": ["tons", "tons"],
                  "value": [10.0, 20.0], "dms_mode": [1, 2], "fr_inmode": [None, 3],
                  "dms_orig": [1, 1], "dms_dest": [2, 2], "sctg2": [1, 1]}).write_parquet(silver)
    monkeypatch.setattr(faf5_gold, "SILVER_PATH", silver)
    monkeypatch.setattr(faf5_gold, "GOLD_DIR", gold)
    faf5_gold.build_gold()
    modes = pl.read_parquet(gold / "mode_mix.parquet").sort("dms_mode")
    assert modes["dms_mode"].to_list() == [1, 2]
    assert modes["tons"].to_list() == [10.0, 20.0]
    assert abs(modes["share"].sum() - 1) < 1e-12
    assert "fr_inmode" not in modes.columns
    corridors = pl.read_parquet(gold / "top_corridors.parquet")
    assert set(corridors["dms_mode"]) == {1, 2}
