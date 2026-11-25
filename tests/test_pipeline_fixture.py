"""Run all nine real transformations on tiny isolated input, never the local FAF dataset."""

import sys

import polars as pl
from openpyxl import Workbook

from freight_intelligence import pipeline
from freight_intelligence.ingestion import faf5
from freight_intelligence.transformations.faf5_silver import YEARS


def test_complete_pipeline_on_isolated_small_source(tmp_path, monkeypatch, capsys):
    raw = tmp_path / "data/raw/faf5/forecast"
    raw.mkdir(parents=True)
    csv = raw / "FAF5.5.1_HiLoForecasts.csv"
    dimensions = ["fr_orig", "dms_orig", "dms_dest", "fr_dest", "dms_mode", "fr_inmode",
                  "fr_outmode", "sctg2", "trade_type", "dist_band"]
    data = {name: [1, 2] for name in dimensions}
    data["dms_dest"] = [2, 1]
    data.update({f"{metric}_{year}": [10.0, 20.0]
                 for metric in ["tons", "value", "tmiles"] for year in YEARS})
    pl.DataFrame(data).write_csv(csv)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Commodity (SCTG2)"
    sheet.append(["Code", "Description"])
    sheet.append([1, "First commodity"])
    sheet.append([2, "Second commodity"])
    workbook.save(raw / "FAF5_metadata.xlsx")
    workbook.close()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(faf5, "CSV_PATH", csv)
    # Keep the actual pipeline in the isolated fixture root instead of the user's repo.
    monkeypatch.setattr(pipeline.os, "chdir", lambda path: None)
    monkeypatch.setattr(sys, "argv", ["pipeline"])
    pipeline.main()
    assert "Pipeline completed successfully" in capsys.readouterr().out
    assert pl.read_parquet("data/bronze/faf5/faf5_forecasts.parquet").height == 2
    assert pl.read_parquet("data/silver/faf5/faf5_long.parquet").height == 78
    gold = tmp_path / "data/gold/faf5"
    outputs = list(gold.glob("*.parquet"))
    assert len(outputs) == 11
    assert all(not pl.read_parquet(path).is_empty() for path in outputs)
    annual = pl.read_parquet(gold / "annual_kpis.parquet")
    assert annual.height == 39
    assert annual.filter((pl.col("year") == 2025) & (pl.col("metric_type") == "tons"))["total_value"].item() == 30
    assert pl.read_parquet(gold / "commodity_growth.parquet")["cagr"].to_list() == [0.0, 0.0]
    assert not list(gold.glob(".*.parquet"))
