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
        help="Skip steps only when all expected outputs exist.",
    )
    args = parser.parse_args()

    os.chdir(Path(__file__).resolve().parents[1])

    steps = [
        ("Bronze ingestion", ingest_faf5, ["data/bronze/faf5/faf5_forecasts.parquet"]),
        ("Silver transformation", build_silver, ["data/silver/faf5/faf5_long.parquet"]),
        (
            "Gold analytics",
            build_gold,
            [
                "data/gold/faf5/annual_kpis.parquet",
                "data/gold/faf5/mode_mix.parquet",
                "data/gold/faf5/top_corridors.parquet",
                "data/gold/faf5/commodity_mix.parquet",
            ],
        ),
        (
            "Commodity lookup",
            build_commodity_lookup,
            ["data/gold/faf5/commodity_lookup.parquet"],
        ),
        ("Annual growth", build_annual_growth, ["data/gold/faf5/annual_growth.parquet"]),
        ("Annual CAGR", build_annual_cagr, ["data/gold/faf5/annual_cagr.parquet"]),
        (
            "Commodity growth",
            build_commodity_growth,
            ["data/gold/faf5/commodity_growth.parquet"],
        ),
        (
            "Commodity share change",
            build_commodity_share_change,
            ["data/gold/faf5/commodity_share_change.parquet"],
        ),
        (
            "Corridor analysis",
            build_corridor_analysis,
            [
                "data/gold/faf5/corridor_summary.parquet",
                "data/gold/faf5/corridor_concentration.parquet",
            ],
        ),
    ]

    for name, step, outputs in steps:
        if args.skip_existing and all(Path(output).is_file() for output in outputs):
            print(f"\n===== {name}: skipped (outputs exist) =====", flush=True)
            continue

        print(f"\n===== {name} =====", flush=True)
        step()

    print("\nPipeline completed successfully.", flush=True)


if __name__ == "__main__":
    main()
