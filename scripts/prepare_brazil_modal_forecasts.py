"""Evaluate the reviewed 2010–2024 port and oil-pipeline histories separately."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from freight_intelligence.brazil_modal_forecasts import SERIES
from freight_intelligence.brazil_modes import load_modes
from freight_intelligence.ml.historical_evaluation import historical_report

ROOT = Path(__file__).resolve().parents[1]


def prepare(output):
    data, provenance = load_modes()
    selected = data.filter(pl.col("indicator").is_in(list(SERIES))).sort("indicator", "year")
    observations = selected.select(pl.col("indicator").alias("metric_type"), "year",
                                   pl.col("value").alias("total_value"))
    sources = selected.select("indicator", "unit", "scope", "source_url", "source_page").unique().sort("indicator")
    manifest = {
        "dataset_id": "brazil_port_and_transpetro_rounded_histories_2010_2024",
        "source": "Reviewed Infra S.A./ONTL chart-label snapshot; original ANTAQ/Transpetro populations",
        "retrieved_at": provenance["prepared_on"], "record_kind": "historical_observations",
        "scope": "Rounded reported port handling and Transpetro oil/product volumes, evaluated separately; not unique national shipments, modal shares or current live demand",
        "units": {name: contract[1] for name, contract in SERIES.items()},
    }
    report = historical_report(observations.write_csv().encode(), json.dumps(manifest).encode(),
                               min_train_points=8, test_points=3, forecast_years=3)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "forecast.zip").write_bytes(report)
    metadata = {
        "schema_version": 1, "prepared_on": datetime.now(UTC).date().isoformat(),
        "source_end_year": 2024, "test_years": [2022, 2023, 2024],
        "forecast_years": [2025, 2026, 2027], "forecast_vintage": "2024 observation cutoff",
        "series": sources.to_dicts(), "source_documents": [record for record in provenance["sources"]
                                                             if record["url"] in set(selected["source_url"])],
        "interpretation": "Vintage forecasts from the reviewed 2010–2024 source edition. Forecast years can already be past calendar years; they remain model estimates, never newly observed data. Rounded histories and different statistical populations remain separate. No uncertainty intervals or future accuracy guarantee.",
        "newer_references": "Separate 2025 ANTAQ handling references are not appended to this older rounded history without a source-edition reconciliation",
        "files": [{"path": "forecast.zip", "bytes": len(report), "sha256": hashlib.sha256(report).hexdigest()}],
    }
    (output / "provenance.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return observations.height


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "deployment/brazil_modal_forecasts")
    args = parser.parse_args()
    print(f"Evaluated {prepare(args.output)} reviewed annual observations")
