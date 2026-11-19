# Current delivery and remaining work

2026-11-19 implementation: [775 state OD pairs](brazil_road_od.md), 28 source and destination categories, independently reconciled to 1,368,627,704 integer tonnes for 2025. Filtered UI/API and full CSV; archived yearbook remains separate. Publication is verified per delivery.

This page describes the current main-branch implementation. Dated handoff entries
and the recovered original chat are historical. Current verification runs are
listed in [CI Pipeline](https://github.com/DiegoTDDD/freight-intelligence/actions/workflows/ci_pipeline.yml).

## Delivered portfolio scope

| Area | Delivered behavior |
| --- | --- |
| Data engineering | Bronze/Silver/Gold pipeline; full real run verified, 2,503,352 Bronze and 97,630,728 Silver rows |
| Analytics | FAF indicators, commodities, domestic modes and corridors, with source units and scenario labels |
| Forecasting | Baselines and reserved tests for ANTT railway, ANAC paid-stage subtotals, port handling and Transpetro oil/product volumes; the last two retain a 2024 source cutoff and reserved 2022–2024 tests |
| Optimization | Tested constrained transport solver, editable scenarios and comparisons; scenario costs are not measured savings |
| Dashboard | Published Streamlit app; English default; Portuguese controls and core notices for modal, truck, gas and air workspaces |
| Real-road routing | Separate OSRM car-reference and Valhalla truck engines; explicit truck profile, map, instructions and GeoJSON |
| Brazil | 145 scoped annual indicators across five modes; detailed rail; 600 monthly ANP gas records (2021–2025) with source diagnostics; 624 ANAC monthly aggregates and 36,860 recent monthly airport-pair aggregates; 55 ANTAQ reference/monthly records plus 21 paired regional cabotage shares and 510 OD pairs covering all 98 origins in the reviewed cabotage table; 28 road panel months (56 account-category rows) plus 12 archived yearbook months and 16 RGI pairs |
| Public API | Documented read-only HTTP API under `/api`; configured key/user permissions retained; private local plans excluded |
| Reproducibility | Pinned container runtimes, snapshot hashes and verified recovery archives |
| CI and deployment | Windows/Linux tests, API/container and dashboard checks; deploy only the exact tested main revision |
| GitHub delivery | PR #1 merged; main is the published branch |

Historical baseline evidence (`bd3f608`, 2026-11-13): 349 lightweight tests passed locally, all five remote checks
passed, and the public gas API matched the reviewed records and source hashes.
The dashboard/API server passed offline/read-only checks within 512 MiB.
The heavy full pipeline was verified previously and was not rerun for this update.

- [Live dashboard](https://loginexus-dashboard-preview.onrender.com/)
- [Public API](https://loginexus-dashboard-preview.onrender.com/api/docs)
- [Baseline CI evidence](https://github.com/DiegoTDDD/freight-intelligence/actions/runs/43362883453)
- [Brazilian coverage and quality](brazil_modes.md)
- [Truck routing and provider policy](truck_routing.md)

## Remaining work, in priority order

1. **Data refresh:** [ANP 2025 and ANTT road revision auditing](source_refresh.md)
   automates bounded retrieval, candidate validation/review and revision reporting. Extend this to other
   sources/years and integrate reviewed candidates through the normal CI gate;
   a source revision is not automatically an improvement in quality.
2. **Road freight:** extend compatible movement history before July 2024
   and regional flows beyond the [16 published RGI pairs](brazil_road.md).
   The [reviewed panel history](brazil_road_history.md) now covers 28 months,
   July 2024–October 2026, with N/S components and explicit partial-year flags.
   The archived yearbook annual indicator sums its monthly labels to 1,368,699,651
   tonnes, which rounds to the summary's 1.4 billion. The publication's 1.165-billion
   regional denominator remains separate; its exact scope is not inferred.
   Within-city trips are outside the current MDF-e scope. RGI pairs are groups
   of municipalities, not operational itineraries.
3. **Water freight:** [inland/coastal and regional reference analyses](brazil_water.md)
   and twelve 2025 port-handling months plus 21 paired regional cabotage shares and 510 OD pairs covering all 98 origins in the reviewed cabotage table are implemented.
   Extend the monthly history, port/state-level OD and
   fuller corridor detail; current state endpoints are marginal totals only.
4. **Air freight:** [monthly history, airports, stage pairs and reserved forecasts](brazil_air.md)
   are implemented. Further refreshes require reviewing source revisions and
   maintaining explicit Brazilian-endpoint and missing-field coverage.
5. **Pipelines:** [gas history and diagnostics](brazil_gas_history.md) cover 2021–2025;
   the 33 missing 2025 cells are traced to source points/dates, without imputation.
   Extend earlier years only after their unit contracts are verified, and add
   other oil-pipeline operators/mineral pipelines where reliable data exists.
   Gas receipt/delivery point subtotals can repeat transfers and are not national supply.
6. **Rail:** extend beyond the available federal-concession reports and handle
   repeated movements only where source identifiers support doing so.
7. **Operational optimization:** connect verified real demand, capacity and costs
   to the solver and evaluate realized outcomes. Synthetic scenario differences
   are not evidence of actual savings.
8. **Broader forecasting:** ANAC paid-stage subtotals, port handling and Transpetro
   oil/product vintage reports now complement railway evaluation. Extend reliable histories for remaining targets and evaluate
   them on reserved periods. Short histories and changing coverage cannot justify
   claims of complete national demand. FAF projections remain scenarios.

The newer modal/truck/gas/air controls and core notices support Portuguese without
changing internal choices, source identifiers, exports or the English default.
Original provenance documents and source-field values retain their source language.

## Additional requirements for commercial operation

Truck dispatch needs verified regional restrictions/current conditions and an
appropriate provider agreement; toll pricing and driver-hours compliance are not
implemented. Free demonstration infrastructure has no uptime/permanence guarantee.
Commercial hosting needs operational monitoring and recovery procedures. The public
API currently shares hosting with the dashboard; independent hosting is a separate
deployment choice. Private user data would require a protected dashboard and
user-specific persistence before it could be accepted.

These requirements are distinct from the delivered original portfolio roadmap.
No paid services were purchased. The local hourly development automation is paused;
it is separate from repository data-refresh workflows.

## Portfolio review when the demo sleeps

The [README](../README.md) inventories all workspaces and delivery components,
includes screenshots and explains the shared free-host limits. The generated
[static evidence report](portfolio_evidence.md) exposes counts, observed subtotals,
all ANAC candidate test scores and source-quality reconciliations without running
a server. CI checks this report against validated public snapshots. The local
Docker demo packages the same public data and does not require the large pipeline.
