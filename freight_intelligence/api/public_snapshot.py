"""Public snapshot readers shared by separate API and dashboard hosting."""

from pathlib import Path

from freight_intelligence.api.app import create_app

PROJECT = Path(__file__).resolve().parents[2]


def snapshot_api(root: Path):
    """Pin every reader to versioned public data, never local saved business plans."""
    return create_app(
        gold_dir=root / "data/gold/faf5",
        model_dir=root / "models/faf5/annual",
        evaluation_dir=root / "artifacts/evaluation/annual",
        transport_dir=root / "artifacts/optimization/transport",
        brazil_dir=PROJECT / "deployment/brazil_modes",
        gas_dir=PROJECT / "deployment/brazil_gas",
        water_dir=PROJECT / "deployment/brazil_water",
        road_dir=PROJECT / "deployment/brazil_road",
        air_dir=PROJECT / "deployment/brazil_air",
        gas_history_dir=PROJECT / "deployment/brazil_gas_history",
        modal_forecasts_dir=PROJECT / "deployment/brazil_modal_forecasts",
        trip_rules_dir=PROJECT / "deployment/trip_planning",
        weekly_rules_dir=PROJECT / "deployment/duty_review",
    )
