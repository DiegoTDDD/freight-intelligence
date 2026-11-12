import pytest

from freight_intelligence.ingestion import faf5
from freight_intelligence.transformations import faf5_silver
from freight_intelligence.utils.atomic_output import atomic_output


def test_failed_write_preserves_previous_complete_output(tmp_path):
    destination = tmp_path / "output.parquet"
    destination.write_bytes(b"old complete output")
    with pytest.raises(RuntimeError), atomic_output(destination) as staged:
        staged.write_bytes(b"partial new output")
        raise RuntimeError("writer interrupted")
    assert destination.read_bytes() == b"old complete output"
    assert list(tmp_path.iterdir()) == [destination]


def test_new_destination_does_not_appear_when_writer_fails(tmp_path):
    destination = tmp_path / "new.parquet"
    with pytest.raises(RuntimeError), atomic_output(destination) as staged:
        staged.write_bytes(b"partial")
        raise RuntimeError("failed")
    assert not list(tmp_path.iterdir())


def test_complete_write_replaces_previous_output(tmp_path):
    destination = tmp_path / "output.parquet"
    destination.write_bytes(b"old")
    with atomic_output(destination) as staged:
        assert destination.read_bytes() == b"old"
        staged.write_bytes(b"complete replacement")
    assert destination.read_bytes() == b"complete replacement"
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize("module", [faf5, faf5_silver])
def test_layer_sink_failure_keeps_published_output(tmp_path, monkeypatch, module):
    import polars as pl

    directory = tmp_path / "layer"
    directory.mkdir()
    filename = "faf5_forecasts.parquet" if module is faf5 else "faf5_long.parquet"
    output = directory / filename
    output.write_bytes(b"previous output")
    if module is faf5:
        monkeypatch.setattr(module, "BRONZE_DIR", directory)
        monkeypatch.setattr(module, "CSV_PATH", tmp_path / "fixture.csv")
        (tmp_path / "fixture.csv").write_text("value\n1\n")
    else:
        monkeypatch.setattr(module, "SILVER_DIR", directory)
        source = tmp_path / "bronze.parquet"
        dimensions = ["fr_orig", "dms_orig", "dms_dest", "fr_dest", "fr_inmode", "dms_mode",
                      "fr_outmode", "sctg2", "trade_type", "dist_band"]
        pl.DataFrame({**{key: [1] for key in dimensions},
                      **{f"{metric}_{year}": [1.0] for metric in ("tons", "value", "tmiles")
                         for year in module.YEARS}}).write_parquet(source)
        monkeypatch.setattr(module, "BRONZE_PATH", source)

    def interrupted(self, path, **kwargs):
        path.write_bytes(b"partial")
        raise RuntimeError("interrupted sink")

    monkeypatch.setattr(pl.LazyFrame, "sink_parquet", interrupted)
    with pytest.raises(RuntimeError):
        (module.ingest_faf5 if module is faf5 else module.build_silver)(force=True)
    assert output.read_bytes() == b"previous output"
    assert list(directory.iterdir()) == [output]


def test_bronze_publishes_complete_parquet_from_small_csv(tmp_path, monkeypatch):
    import polars as pl

    monkeypatch.setattr(faf5, "BRONZE_DIR", tmp_path / "bronze")
    source = tmp_path / "source.csv"
    source.write_text("id,value\n1,10\n2,20\n")
    monkeypatch.setattr(faf5, "CSV_PATH", source)
    result = faf5.ingest_faf5(force=True)
    assert pl.read_parquet(result).to_dicts() == [{"id": 1, "value": 10}, {"id": 2, "value": 20}]
    assert list(result.parent.iterdir()) == [result]
