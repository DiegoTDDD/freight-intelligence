import subprocess
import sys
from pathlib import Path

STEP_NAMES = (
    "ingest_faf5",
    "build_silver",
    "build_gold",
    "build_commodity_lookup",
    "build_annual_growth",
    "build_annual_cagr",
    "build_commodity_growth",
    "build_commodity_share_change",
    "build_corridor_analysis",
)


def patch_steps(monkeypatch, pipeline, called):
    for name in STEP_NAMES:
        if name in ("ingest_faf5", "build_silver"):
            monkeypatch.setattr(
                pipeline,
                name,
                lambda force=False, name=name: called.append((name, force)),
            )
        else:
            monkeypatch.setattr(
                pipeline,
                name,
                lambda name=name: called.append((name, None)),
            )


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


def test_skip_existing_skips_steps_with_all_outputs(monkeypatch):
    from freight_intelligence import pipeline

    called = []
    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--skip-existing"])
    monkeypatch.setattr(pipeline.os, "chdir", lambda path: None)
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    patch_steps(monkeypatch, pipeline, called)

    pipeline.main()

    assert called == []


def test_default_run_executes_all_steps_and_forces_bronze_and_silver(
    monkeypatch,
):
    from freight_intelligence import pipeline

    called = []
    monkeypatch.setattr(sys, "argv", ["pipeline.py"])
    monkeypatch.setattr(pipeline.os, "chdir", lambda path: None)
    patch_steps(monkeypatch, pipeline, called)

    pipeline.main()

    assert [name for name, force in called] == list(STEP_NAMES)
    assert called[0] == ("ingest_faf5", True)
    assert called[1] == ("build_silver", True)


def test_missing_bronze_rebuilds_dependent_steps(monkeypatch):
    from freight_intelligence import pipeline

    called = []
    missing_output = Path("data/bronze/faf5/faf5_forecasts.parquet")

    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--skip-existing"])
    monkeypatch.setattr(pipeline.os, "chdir", lambda path: None)
    monkeypatch.setattr(
        Path,
        "is_file",
        lambda self: self != missing_output,
    )
    patch_steps(monkeypatch, pipeline, called)

    pipeline.main()

    assert [name for name, force in called] == [
        "ingest_faf5",
        "build_silver",
        "build_gold",
        "build_annual_growth",
        "build_annual_cagr",
        "build_commodity_growth",
        "build_commodity_share_change",
        "build_corridor_analysis",
    ]
    assert ("ingest_faf5", False) in called
    assert ("build_silver", True) in called


def test_missing_lookup_rebuilds_only_commodity_dependents(monkeypatch):
    from freight_intelligence import pipeline

    called = []
    missing_output = Path("data/gold/faf5/commodity_lookup.parquet")

    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--skip-existing"])
    monkeypatch.setattr(pipeline.os, "chdir", lambda path: None)
    monkeypatch.setattr(
        Path,
        "is_file",
        lambda self: self != missing_output,
    )
    patch_steps(monkeypatch, pipeline, called)

    pipeline.main()

    assert [name for name, force in called] == [
        "build_commodity_lookup",
        "build_commodity_growth",
        "build_commodity_share_change",
    ]


def test_plan_never_invokes_steps_and_tracks_dependency_rebuilds(monkeypatch, capsys):
    import json

    from freight_intelligence import pipeline

    called = []
    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--plan", "--skip-existing"])
    monkeypatch.setattr(pipeline.os, "chdir", lambda path: None)
    missing = Path("data/bronze/faf5/faf5_forecasts.parquet")
    monkeypatch.setattr(Path, "is_file", lambda self: self != missing)
    patch_steps(monkeypatch, pipeline, called)
    pipeline.main()
    plan = json.loads(capsys.readouterr().out)
    assert plan["plan_only"] is True
    assert called == []
    steps = {row["step"]: row for row in plan["steps"]}
    assert steps["Bronze ingestion"]["missing_outputs"] == [str(missing).replace('\\', '/')]
    assert steps["Silver transformation"]["action"] == "run"
    assert "upstream" in steps["Silver transformation"]["reason"]
    assert steps["Commodity lookup"]["action"] == "skip"
    assert steps["Gold analytics"]["large_data_step"] is True


def test_plan_default_reports_full_rebuild_without_executing(monkeypatch, capsys):
    import json

    from freight_intelligence import pipeline

    called = []
    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--plan"])
    monkeypatch.setattr(pipeline.os, "chdir", lambda path: None)
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    patch_steps(monkeypatch, pipeline, called)
    pipeline.main()
    plan = json.loads(capsys.readouterr().out)
    assert called == []
    assert len(plan["steps"]) == 9
    assert all(row["action"] == "run" for row in plan["steps"])
