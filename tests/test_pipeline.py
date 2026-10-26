import subprocess
import sys
from pathlib import Path


def test_pipeline_help_does_not_run_steps():
    result = subprocess.run(
        [sys.executable, "-m", "freight_intelligence.pipeline", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "--skip-existing" in result.stdout
    assert "Bronze ingestion" not in result.stdout
    assert "Pipeline completed successfully." not in result.stdout


def test_skip_existing_skips_steps_with_all_outputs(monkeypatch, tmp_path):
    from freight_intelligence import pipeline

    called = []
    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--skip-existing"])
    monkeypatch.setattr(pipeline.os, "chdir", lambda path: None)
    monkeypatch.setattr(
        Path,
        "is_file",
        lambda self: True,
    )

    for name in (
        "ingest_faf5",
        "build_silver",
        "build_gold",
        "build_commodity_lookup",
        "build_annual_growth",
        "build_annual_cagr",
        "build_commodity_growth",
        "build_commodity_share_change",
        "build_corridor_analysis",
    ):
        monkeypatch.setattr(
            pipeline,
            name,
            lambda name=name: called.append(name),
        )

    pipeline.main()

    assert called == []




def test_skip_existing_runs_step_when_output_is_missing(monkeypatch):
    from freight_intelligence import pipeline

    called = []
    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--skip-existing"])
    monkeypatch.setattr(pipeline.os, "chdir", lambda path: None)

    missing_output = Path("data/bronze/faf5/faf5_forecasts.parquet")
    monkeypatch.setattr(Path, "is_file", lambda self: self != missing_output)

    for name in (
        "ingest_faf5",
        "build_silver",
        "build_gold",
        "build_commodity_lookup",
        "build_annual_growth",
        "build_annual_cagr",
        "build_commodity_growth",
        "build_commodity_share_change",
        "build_corridor_analysis",
    ):
        monkeypatch.setattr(
            pipeline,
            name,
            lambda name=name: called.append(name),
        )

    pipeline.main()

    assert called == ["ingest_faf5"]
