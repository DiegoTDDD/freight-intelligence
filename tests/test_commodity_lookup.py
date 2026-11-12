import io
import sys

import polars as pl
from openpyxl import Workbook

from freight_intelligence.transformations import commodity_lookup


def test_lookup_writes_unicode_parquet_with_cp1252_stdout(tmp_path, monkeypatch):
    metadata = tmp_path / "metadata.xlsx"
    output = tmp_path / "gold" / "commodity_lookup.parquet"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Commodity (SCTG2)"
    sheet.append(["Code", "Description"])
    sheet.append([2, "  Grãos 漢字  "])
    sheet.append([1, "Animals"])
    sheet.append([None, "Ignored"])
    sheet.append([3, None])
    workbook.save(metadata)
    workbook.close()

    monkeypatch.setattr(commodity_lookup, "INPUT_PATH", metadata)
    # Keep printed paths independent of the user's Windows username encoding.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(commodity_lookup, "OUTPUT_PATH", output.relative_to(tmp_path))
    stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stdout)

    commodity_lookup.main()

    result = pl.read_parquet(output)
    assert result.to_dicts() == [
        {"sctg2": 1, "commodity_name": "Animals"},
        {"sctg2": 2, "commodity_name": "Grãos 漢字"},
    ]
    stdout.flush()
    assert b"Categories: 2" in stdout.buffer.getvalue()
