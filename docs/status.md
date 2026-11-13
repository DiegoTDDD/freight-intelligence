# Current delivery and remaining work

This page describes the current main-branch implementation. Dated handoff entries
and the recovered original chat are historical. Current verification runs are
listed in [CI Pipeline](https://github.com/DiegoTDDD/freight-intelligence/actions/workflows/ci_pipeline.yml).

## Delivered portfolio scope

| Area | Delivered behavior |
| --- | --- |
| Data engineering | Bronze/Silver/Gold pipeline; full real run verified, 2,503,352 Bronze and 97,630,728 Silver rows |
| Analytics | FAF indicators, commodities, domestic modes and corridors, with source units and scenario labels |
| Forecasting | Baselines, temporal validation and reserved tests; observed ANTT railway history 2006–2025 |
| Optimization | Tested constrained transport solver, editable scenarios and comparisons; scenario costs are not measured savings |
| Dashboard | Published Streamlit app; English default, optional Portuguese translation |
| Real-road routing | Separate OSRM car-reference and Valhalla truck engines; explicit truck profile, map, instructions and GeoJSON |
| Brazil | 122 scoped annual indicators across five modes, detailed railway data, 120 monthly ANP gas records and 43 ANTAQ water references |
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

1. **Data refresh:** [ANP 2025 revision auditing](source_refresh.md) automates bounded
   retrieval, candidate validation and revision reporting. Extend this to other
   sources/years and integrate reviewed candidates through the normal CI gate;
   a source revision is not automatically an improvement in quality.
2. **Road freight:** reconcile the official 1.4/1.165-billion-tonne discrepancy;
   extend movement history and regional flows. Within-city trips are outside the
   current MDF-e scope.
3. **Water freight:** [inland/coastal and regional reference analyses](brazil_water.md)
   are implemented. Extend them to monthly source records, paired OD flows and
   fuller corridor detail; current state endpoints are marginal totals only.
4. **Air freight:** extend paid-cargo aggregates to airport/origin/destination and
   finer time periods, preserving the paid/unpaid and domestic/international scope.
5. **Pipelines:** extend gas history beyond 2025, investigate 33 missing daily cells,
   and add other oil-pipeline operators/mineral pipelines where reliable data exists.
   Gas receipt/delivery point subtotals can repeat transfers and are not national supply.
6. **Rail:** extend beyond the available federal-concession reports and handle
   repeated movements only where source identifiers support doing so.
7. **Operational optimization:** connect verified real demand, capacity and costs
   to the solver and evaluate realized outcomes. Synthetic scenario differences
   are not evidence of actual savings.
8. **Broader forecasting:** add observed histories for other modes and evaluate
   them on reserved future periods. FAF projections remain scenarios.
9. **Optional translation:** finish Portuguese for newer modal/truck/gas screens;
   English remains the project default.

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
