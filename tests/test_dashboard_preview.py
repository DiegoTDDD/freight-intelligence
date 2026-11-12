import hashlib
import importlib.util
import json
from pathlib import Path

import polars as pl
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_dashboard_preview", ROOT / "scripts/prepare_dashboard_preview.py")
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


def test_snapshot_copies_only_allowlisted_data_and_preserves_source(tmp_path):
    source = tmp_path / "source"
    gold = source / "data/gold/faf5"
    gold.mkdir(parents=True)
    for name in preview.GOLD_FILES:
        pl.DataFrame({"value": [1]}).write_parquet(gold / name)
    (source / ".env").write_text("DO_NOT_COPY=secret")
    raw = source / "data/raw/faf5"
    raw.mkdir(parents=True)
    (raw / "private.csv").write_text("private")
    output = tmp_path / "snapshot"
    original = (gold / "annual_kpis.parquet").read_bytes()
    count, _ = preview.prepare(source, output)
    assert count == 11
    assert not (output / ".env").exists()
    assert not (output / "data/raw/faf5/private.csv").exists()
    assert (gold / "annual_kpis.parquet").read_bytes() == original
    manifest = json.loads((output / "snapshot_manifest.json").read_text())
    for record in manifest["files"]:
        assert hashlib.sha256((output / record["path"]).read_bytes()).hexdigest() == record["sha256"]
    with pytest.raises(ValueError, match="already exists"):
        preview.prepare(source, output)
