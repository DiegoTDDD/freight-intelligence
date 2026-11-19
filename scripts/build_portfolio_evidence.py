"""Build a static, host-independent portfolio report from validated public snapshots."""

import argparse
from pathlib import Path

import polars as pl

from freight_intelligence.brazil_air import load_air
from freight_intelligence.brazil_gas_history import load_gas_history
from freight_intelligence.brazil_gas_results import load_gas
from freight_intelligence.brazil_modes import load_modes
from freight_intelligence.brazil_road import load_road, load_road_monthly
from freight_intelligence.brazil_water import load_water, load_water_pairs

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/portfolio_evidence.md"


def table(headers, rows):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")

    return "\n".join("| " + " | ".join(map(cell, row)) + " |"
                     for row in [headers, ["---"] * len(headers), *rows])


def render():
    air, air_metadata, report = load_air()
    gas, _, _ = load_gas()
    historical_gas, _, _ = load_gas_history()
    water, _ = load_water()
    water_pairs, _ = load_water_pairs()
    road, _ = load_road()
    road_months, road_metadata = load_road_monthly()
    modes, _ = load_modes()
    counts = table(["Public snapshot", "Records", "Scope"], [
        ["Five-mode annual atlas", modes.height, "Separately scoped indicators; incompatible units are not summed"],
        ["ANAC monthly history", air["monthly"].height, "2000–2025; domestic/international; Brazil-linked stages"],
        ["ANAC monthly airport pairs", air["pairs"].height, "2024–2025; reported stages, not unique consignments"],
        ["ANAC airport source codes", air["airports"].height, "Reference codes present in the selected pair population"],
        ["ANP gas operator/direction/month", gas.height + historical_gas.height,
         f"{historical_gas['year'].min()}–{gas['year'].max()}; coverage changes; not unique national supply"],
        ["ANTAQ references and monthly rows", water.height, "43 annual/regional references plus twelve 2025 port-handling months"],
        ["ANTAQ paired regional cabotage shares", water_pairs.height,
         "2025 original region-to-region fractions; offshore and undetermined origins retained"],
        ["ANTT road monthly totals", road_months.height, "2025 published Chart 45 labels"],
        ["ANTT regional road pairs", road.height, "16 published RGI pairs; not municipalities or truck itineraries"],
    ])
    annual = air["annual"].filter(pl.col("year") == air_metadata["end_year"]).sort("nature")
    air_table = table(["Year", "Nature", "Paid cargo (kg)", "Free cargo (kg)", "Mail (kg)",
                       "Missing paid-cargo fields"], [
        [r["year"], r["nature"], f'{r["paid_cargo_kg"]:,}', f'{r["free_cargo_kg"]:,}',
         f'{r["mail_kg"]:,}', r["missing_paid_cargo_kg"]] for r in annual.to_dicts()
    ])
    scores = report["scores"].filter(pl.col("phase") == "test").sort("metric_type", "model")
    score_table = table(["Observed subtotal", "Baseline", "Selected on validation", "Test WAPE"], [
        [r["metric_type"], r["model"], "Yes" if r["selected"] else "No", f'{r["wape"]:.2%}']
        for r in scores.to_dicts()
    ])
    water_months = water.filter(pl.col("dataset") == "port_monthly").sort("category")
    water_table = table(["Month", "Displayed port handling (tonnes)"], [
        [r["category"], f'{r["value"]:,.0f}'] for r in water_months.to_dicts()
    ])
    pair_table = table(["Origin region", "Destination region", "Share of full panel population"], [
        [r["origin_region"], r["destination_region"], f'{r["share_of_cabotage"]:.6%}']
        for r in water_pairs.sort("share_of_cabotage", descending=True).to_dicts()
    ])
    missing = gas.group_by("point_type").agg(pl.col("missing_daily_values").sum()).sort("point_type")
    missing_table = table(["2025 point direction", "Missing daily cells"], [
        [r["point_type"], r["missing_daily_values"]] for r in missing.to_dicts()
    ])
    road_total = road_metadata["reconciliation"]["annual_tonnes"]
    return f"""# Portfolio evidence without a running server

This report is generated from the repository's hash-checked public snapshots.
It can be read on GitHub or from a local clone while the interactive demo sleeps
or is unavailable. It does not contact Render, download raw sources, train models,
run the solver or execute the large FAF pipeline.

Rebuild: `python scripts/build_portfolio_evidence.py`
Check for drift: `python scripts/build_portfolio_evidence.py --check`

## Bundled coverage

{counts}

The full local FAF run previously produced 2,503,352 Bronze and 97,630,728 Silver
rows. Those raw/large layers are not checked into Git. The compact public demo
aggregates are versioned in [deployment](../deployment/), with manifests and hashes.

## ANAC observed cargo subtotals

{air_table}

Paid cargo, free cargo and mail remain separate. Missing source fields are
excluded from sums and counted, never invented as observed zero cargo. One
consignment can appear on more than one stage. See [scope and sources](brazil_air.md).

## Forecast results, including competing baselines

Training/model selection uses validation through 2022; 2023–2025 are reserved
for the final test. The table includes every candidate, not only the selected one.

{score_table}

Both validation-selected models have worse reserved-test errors than
persistence. This is a disclosed result, not a reason to select again on test
data. Future forecasts are point estimates without accuracy guarantees.
The [portable report ZIP](../deployment/brazil_air/forecast.zip) contains scores,
predictions, forecasts and source/split metadata.

The independent [ANTT railway evaluation](brasil.md) covers 2006–2025;
validation-selected reserved-test WAPE is 4.75% TU and 1.61% TKU. Railway,
airport-stage and FAF scenario populations must not be treated as equivalent.

## Monthly port handling

{water_table}

Displayed monthly sum: **{water_months['value'].sum():,.0f} tonnes**. The panel's annual
headline is **1,402,731,833 tonnes**. The one-tonne display discrepancy is retained,
with no invented allocation to a month. These are handling movements in both
directions, not unique cargo or paired OD routes. The rounded annual report is
a separate edition. See [the source and filters](brazil_water.md) and
[downloadable source-derived table](../deployment/brazil_water/water.csv).

## Paired regional cabotage distribution

{pair_table}

These 21 pairs are read directly from the original ANTAQ Sankey export, not
constructed from separate origin/destination totals. Stored fractions reconcile
to one; table percentages are rounded for display. Filtering keeps the original
full-population denominator. They do not identify individual ports or nautical
itineraries and must not be scaled by a different annual/handling total.
The [original XLSX export](../deployment/brazil_water/cabotage_region_pairs_2025.xlsx)
and [unrounded derived CSV](../deployment/brazil_water/coastal_region_pairs.csv)
are versioned with hashes and [reviewed filter/period context](brazil_water.md#paired-regional-cabotage-shares).

## Gas source quality and road reconciliation

{missing_table}

The 2025 missing cells trace to Garuva receipts on January 1–31 and RPBC/São
Bernardo do Campo deliveries on May 31. The source leaves them blank; no cause
or volume is inferred. [Historical coverage and quality](brazil_gas_history.md).

The twelve published road-month labels sum to **{road_total:,} tonnes**.
The separate regional-reference denominator is preserved without guessing
its scope. [Road source reconciliation](brazil_road.md).

## Inspect and reproduce

- [Scenario input example](examples/transport_scenario.json): explicit synthetic
  costs/capacities, balance constraints and infeasibility checks; no actual savings claim.
- [Solver and result exports](transport_optimization.md) and [scenario comparison](scenario_planner.md).
- [Public API contracts](api.md) and [local API authentication](api_authentication.md).
- [Saved truck geometry](../deployment/route_examples/sao_paulo_campinas_truck.geojson)
  and [vehicle/map limitations](truck_routing.md).
- [Current verification runs](https://github.com/DiegoTDDD/freight-intelligence/actions/workflows/ci_pipeline.yml).
- [Recovery instructions](recovery.md): source/data archives can be kept independently of Render.
- [Open expansion items](expansion_execution.md): this report does not mark them complete.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != expected:
            raise SystemExit("Portfolio evidence is stale; rebuild it before publishing")
        print("Static portfolio evidence matches validated snapshots")
    else:
        OUTPUT.write_text(expected, encoding="utf-8", newline="\n")
        print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
