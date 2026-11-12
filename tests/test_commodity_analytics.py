"""Exercise downstream commodity transformations with strict Windows console encoding."""

import io
import sys

import polars as pl
import pytest

from freight_intelligence.analytics import commodity_growth, commodity_share_change


@pytest.mark.parametrize("module", [commodity_growth, commodity_share_change])
def test_commodity_analytics_preserve_unicode_with_cp1252_console(tmp_path, monkeypatch, module):
    monkeypatch.chdir(tmp_path)
    source = pl.DataFrame({
        "sctg2": [1, 1, 2, 2], "year": [2017, 2021, 2017, 2021],
        "tons": [100.0, 200.0, 300.0, 300.0], "share": [0.25, 0.4, 0.75, 0.6],
    })
    source.write_parquet("mix.parquet")
    pl.DataFrame({"sctg2": [1, 2], "commodity_name": ["Grãos 漢字", "Other"]}).write_parquet(
        "lookup.parquet"
    )
    monkeypatch.setattr(module, "INPUT_PATH", "mix.parquet")
    monkeypatch.setattr(module, "LOOKUP_PATH", "lookup.parquet")
    monkeypatch.setattr(module, "OUTPUT_PATH", "result.parquet")
    stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stdout)
    module.main()
    stdout.flush()
    result = pl.read_parquet("result.parquet")
    row = result.filter(pl.col("sctg2") == 1).row(0, named=True)
    assert row["commodity_name"] == "Grãos 漢字"
    if module is commodity_growth:
        assert row["absolute_change"] == 100.0
        assert row["cagr"] == pytest.approx(2 ** 0.25 - 1)
    else:
        assert row["share_change"] == pytest.approx(0.15)
    assert b"Records: 2" in stdout.buffer.getvalue()
