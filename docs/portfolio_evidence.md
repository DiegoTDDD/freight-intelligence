# Portfolio evidence without a running server

This report is generated from the repository's hash-checked public snapshots.
It can be read on GitHub or from a local clone while the interactive demo sleeps
or is unavailable. It does not contact Render, download raw sources, train models,
run the solver or execute the large FAF pipeline.

Rebuild: `python scripts/build_portfolio_evidence.py`
Check for drift: `python scripts/build_portfolio_evidence.py --check`

## Bundled coverage

| Public snapshot | Records | Scope |
| --- | --- | --- |
| Five-mode annual atlas | 145 | Separately scoped indicators; incompatible units are not summed |
| ANAC monthly history | 624 | 2000–2025; domestic/international; Brazil-linked stages |
| ANAC monthly airport pairs | 36860 | 2024–2025; reported stages, not unique consignments |
| ANAC airport source codes | 1102 | Reference codes present in the selected pair population |
| ANP gas operator/direction/month | 480 | 2022–2025; coverage changes; not unique national supply |
| ANTAQ references and monthly rows | 55 | 43 annual/regional references plus twelve 2025 port-handling months |
| ANTAQ paired regional cabotage shares | 21 | 2025 original region-to-region fractions; offshore and undetermined origins retained |
| ANTT road monthly totals | 12 | 2025 published Chart 45 labels |
| ANTT regional road pairs | 16 | 16 published RGI pairs; not municipalities or truck itineraries |

The full local FAF run previously produced 2,503,352 Bronze and 97,630,728 Silver
rows. Those raw/large layers are not checked into Git. The compact public demo
aggregates are versioned in [deployment](../deployment/), with manifests and hashes.

## ANAC observed cargo subtotals

| Year | Nature | Paid cargo (kg) | Free cargo (kg) | Mail (kg) | Missing paid-cargo fields |
| --- | --- | --- | --- | --- | --- |
| 2025 | domestic | 431,833,387 | 8,024,379 | 34,353,463 | 88 |
| 2025 | international | 872,045,868 | 3,363,366 | 9,776,955 | 32 |

Paid cargo, free cargo and mail remain separate. Missing source fields are
excluded from sums and counted, never invented as observed zero cargo. One
consignment can appear on more than one stage. See [scope and sources](brazil_air.md).

## Forecast results, including competing baselines

Training/model selection uses validation through 2022; 2023–2025 are reserved
for the final test. The table includes every candidate, not only the selected one.

| Observed subtotal | Baseline | Selected on validation | Test WAPE |
| --- | --- | --- | --- |
| domestic_paid_observed_subtotal | cagr | No | 12.50% |
| domestic_paid_observed_subtotal | linear | Yes | 21.96% |
| domestic_paid_observed_subtotal | persistence | No | 11.61% |
| international_paid_observed_subtotal | cagr | No | 6.61% |
| international_paid_observed_subtotal | linear | Yes | 7.32% |
| international_paid_observed_subtotal | persistence | No | 3.79% |

Both validation-selected models have worse reserved-test errors than
persistence. This is a disclosed result, not a reason to select again on test
data. Future forecasts are point estimates without accuracy guarantees.
The [portable report ZIP](../deployment/brazil_air/forecast.zip) contains scores,
predictions, forecasts and source/split metadata.

The independent [ANTT railway evaluation](brasil.md) covers 2006–2025;
validation-selected reserved-test WAPE is 4.75% TU and 1.61% TKU. Railway,
airport-stage and FAF scenario populations must not be treated as equivalent.

## Port and oil-pipeline evaluation with a 2024 observation cutoff

Each series contains fifteen reviewed rounded annual values, 2010–2024.
Validation ends in 2021; 2022–2024 are reserved for test. Port handling uses
million tonnes and Transpetro oil/product movements use million m³ at 20°C.
They are neither added together nor treated as unique national shipments.

| Rounded historical indicator | Baseline | Selected on validation | Test WAPE |
| --- | --- | --- | --- |
| port_throughput | cagr | No | 1.45% |
| port_throughput | linear | Yes | 2.10% |
| port_throughput | persistence | No | 5.74% |
| transpetro_oil_pipeline_movement | cagr | Yes | 16.91% |
| transpetro_oil_pipeline_movement | linear | No | 27.45% |
| transpetro_oil_pipeline_movement | persistence | No | 15.35% |

The validation-selected port model loses to CAGR on the reserved test; the
selected oil model loses to persistence. No choices are changed after seeing
these results. The bundled forecasts for **2025–2027 are vintage estimates from
a 2024 cutoff**, even for calendar years already past. They are not newly
observed data and are not spliced with a newer source edition.
[Method and scope](brazil_modal_forecasts.md) ·
[portable scores, predictions and source observations](../deployment/brazil_modal_forecasts/forecast.zip).

## Monthly port handling

| Month | Displayed port handling (tonnes) |
| --- | --- |
| 2025-01 | 93,028,512 |
| 2025-02 | 97,302,008 |
| 2025-03 | 115,287,326 |
| 2025-04 | 110,124,907 |
| 2025-05 | 120,338,848 |
| 2025-06 | 121,998,232 |
| 2025-07 | 126,842,293 |
| 2025-08 | 134,234,671 |
| 2025-09 | 121,822,158 |
| 2025-10 | 122,459,471 |
| 2025-11 | 119,549,800 |
| 2025-12 | 119,743,606 |

Displayed monthly sum: **1,402,731,832 tonnes**. The panel's annual
headline is **1,402,731,833 tonnes**. The one-tonne display discrepancy is retained,
with no invented allocation to a month. These are handling movements in both
directions, not unique cargo or paired OD routes. The rounded annual report is
a separate edition. See [the source and filters](brazil_water.md) and
[downloadable source-derived table](../deployment/brazil_water/water.csv).

## Paired regional cabotage distribution

| Origin region | Destination region | Share of full panel population |
| --- | --- | --- |
| ZEE/Plat. Continental | Sudeste | 51.213125% |
| ZEE/Plat. Continental | Sul | 7.256645% |
| Norte | Nordeste | 5.071061% |
| Nordeste | Nordeste | 5.059674% |
| Sudeste | Sudeste | 4.933407% |
| ZEE/Plat. Continental | Nordeste | 4.847250% |
| Sudeste | Nordeste | 4.010315% |
| Nordeste | Sudeste | 3.786131% |
| Sudeste | Sul | 2.876315% |
| Sul | Nordeste | 2.005669% |
| Norte | Norte | 1.945592% |
| Nordeste | Norte | 1.705459% |
| Sudeste | Norte | 1.287457% |
| Norte | Sudeste | 1.049922% |
| Sul | Sul | 0.823380% |
| Nordeste | Sul | 0.794430% |
| Sul | Sudeste | 0.649243% |
| Sul | Norte | 0.422194% |
| Norte | Sul | 0.246249% |
| Indeterminado | Sudeste | 0.016438% |
| Indeterminado | Sul | 0.000043% |

These 21 pairs are read directly from the original ANTAQ Sankey export, not
constructed from separate origin/destination totals. Stored fractions reconcile
to one; table percentages are rounded for display. Filtering keeps the original
full-population denominator. They do not identify individual ports or nautical
itineraries and must not be scaled by a different annual/handling total.
The [original XLSX export](../deployment/brazil_water/cabotage_region_pairs_2025.xlsx)
and [unrounded derived CSV](../deployment/brazil_water/coastal_region_pairs.csv)
are versioned with hashes and [reviewed filter/period context](brazil_water.md#paired-regional-cabotage-shares).

## Gas source quality and road reconciliation

| 2025 point direction | Missing daily cells |
| --- | --- |
| delivery | 2 |
| receipt | 31 |

The 2025 missing cells trace to Garuva receipts on January 1–31 and RPBC/São
Bernardo do Campo deliveries on May 31. The source leaves them blank; no cause
or volume is inferred. [Historical coverage and quality](brazil_gas_history.md).

The twelve published road-month labels sum to **1,368,699,651 tonnes**.
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
