import argparse
import os
from pathlib import Path

from freight_intelligence.analytics.annual_cagr import main as build_annual_cagr
from freight_intelligence.analytics.annual_growth import main as build_annual_growth
from freight_intelligence.analytics.commodity_growth import main as build_commodity_growth
from freight_intelligence.analytics.commodity_share_change import (
    main as build_commodity_share_change,
)
from freight_intelligence.analytics.corridor_analysis import main as build_corridor_analysis
from freight_intelligence.analytics.faf5_gold import build_gold
from freight_intelligence.ingestion.faf5 import ingest_faf5
from freight_intelligence.transformations.commodity_lookup import main as build_commodity_lookup
from freight_intelligence.transformations.faf5_silver import build_silver


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Freight Intelligence pipeline."
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help=(
            "Skip steps whose outputs exist, unless an upstream dependency "
            "must be rebuilt."
        ),
    )
    args = parser.parse_args()

    os.chdir(Path(__file__).resolve().parents[1])

    steps = [
        (
            "Bronze ingestion",
            ingest_faf5,
            ["data/bronze/faf5/faf5_forecasts.parquet"],
            [],
            True,
        ),
        (
            "Silver transformation",
            build_silver,
            ["data/silver/faf5/faf5_long.parquet"],
            ["Bronze ingestion"],
            True,
        ),
        (
            "Gold analytics",
            build_gold,
            [
                "data/gold/faf5/annual_kpis.parquet",
                "data/gold/faf5/mode_mix.parquet",
                "data/gold/faf5/top_corridors.parquet",
                "data/gold/faf5/commodity_mix.parquet",
            ],
            ["Silver transformation"],
            False,
        ),
        (
            "Commodity lookup",
            build_commodity_lookup,
            ["data/gold/faf5/commodity_lookup.parquet"],
            [],
            False,
        ),
        (
            "Annual growth",
            build_annual_growth,
            ["data/gold/faf5/annual_growth.parquet"],
            ["Gold analytics"],
            False,
        ),
        (
            "Annual CAGR",
            build_annual_cagr,
            ["data/gold/faf5/annual_cagr.parquet"],
            ["Gold analytics"],
            False,
        ),
        (
            "Commodity growth",
            build_commodity_growth,
            ["data/gold/faf5/commodity_growth.parquet"],
            ["Gold analytics", "Commodity lookup"],
            False,
        ),
        (
            "Commodity share change",
            build_commodity_share_change,
            ["data/gold/faf5/commodity_share_change.parquet"],
            ["Gold analytics", "Commodity lookup"],
            False,
        ),
        (
            "Corridor analysis",
            build_corridor_analysis,
            [
                "data/gold/faf5/corridor_summary.parquet",
                "data/gold/faf5/corridor_concentration.parquet",
            ],
            ["Gold analytics"],
            False,
        ),
    ]

    rebuilt = {}

    for name, step, outputs, dependencies, accepts_force in steps:
        dependency_rebuilt = any(rebuilt[dependency] for dependency in dependencies)
        outputs_exist = all(Path(output).is_file() for output in outputs)

        if args.skip_existing and outputs_exist and not dependency_rebuilt:
            print(f"\n===== {name}: skipped (outputs exist) =====", flush=True)
            rebuilt[name] = False
            continue

        print(f"\n===== {name} =====", flush=True)

        if accepts_force:
            step(force=not args.skip_existing or dependency_rebuilt)
        else:
            step()

        rebuilt[name] = True

    print("\nPipeline completed successfully.", flush=True)


if __name__ == "__main__":
    main()
