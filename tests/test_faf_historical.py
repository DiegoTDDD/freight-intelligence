import io
import json
from zipfile import ZipFile

import polars as pl
import pytest

from freight_intelligence.ml.faf_historical import prepare_report

DOC = b'2023-09-29 FAF5.5 Annual estimates (Y + 1 through Y + 4) 2017 constant dollars'


def gold():
    data = pl.DataFrame([
        {"metric_type": metric, "year": year, "total_value": float(100 + year - 2017)}
        for metric in ("tons", "value", "tmiles") for year in range(2017, 2026)
    ])
    buffer = io.BytesIO()
    data.write_parquet(buffer)
    return buffer.getvalue()


def test_extract_excludes_forecasts_and_preserves_lineage():
    result = prepare_report(gold(), DOC, "2026-11-11")
    bundle = ZipFile(io.BytesIO(result))
    history = pl.read_csv(bundle.read("observations.csv"))
    assert history.height == 15
    assert history["year"].max() == 2021
    metadata = json.loads(bundle.read("metadata.json"))
    assert metadata["provenance"]["record_kind"] == "historical_estimates"
    assert "historical estimates" in metadata["interpretation"]
    predictions = pl.read_csv(bundle.read("predictions.csv"))
    assert set(predictions.filter(pl.col("phase") == "test")["year"]) == {2021}
    assert set(predictions.filter(pl.col("phase") == "validation")["year"]) == {2019, 2020}
    lineage = json.loads(bundle.read("lineage.json"))
    assert lineage["excluded_years"] == [2022, 2023, 2024, 2025]
    assert len(lineage["gold_sha256"]) == 64
    assert "forecast.csv" not in bundle.namelist()


def test_wrong_documentation_rejected():
    with pytest.raises(ValueError, match="archived"):
        prepare_report(gold(), b'FAF5.7', "2026-11-11")


def test_missing_year_rejected():
    data = pl.read_parquet(gold()).filter(pl.col("year") != 2019)
    buffer = io.BytesIO()
    data.write_parquet(buffer)
    with pytest.raises(ValueError, match="each of three"):
        prepare_report(buffer.getvalue(), DOC, "2026-11-11")
