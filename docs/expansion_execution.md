# Delivery checklist and outstanding requirements

Reviewed **2026-11-20**. This is the authoritative delivery checklist. The
[recovered original roadmap](roteiro_original.md) is historical source material.
Completed items stay closed for their stated coverage. Additional years, sources
or commercial assurance do not silently enlarge an existing acceptance criterion.

The original twelve-stage portfolio and the concrete expansion deliveries below
are implemented and published. This does **not** close the outstanding requirements
in the final table or establish commercial readiness.

## Original roadmap — 12 delivered stages

| ID | Stage | Completion criterion met | Evidence |
| --- | --- | --- | --- |
| O01 | Structure and environment | Installable Python project, declared dependencies and versioned repository | [Project configuration](../pyproject.toml) |
| O02 | Medallion data engineering | Bronze/Silver/Gold implemented; full source run verified, including 97,630,728 Silver rows | [Pipeline](../freight_intelligence/pipeline.py), [execution record](plano_finalizacao.md) |
| O03 | Analytics and quality | KPIs, commodities, domestic modes and corridors with explicit units and validation | [Analytics guide](dashboard.md) |
| O04 | Interactive dashboard | Published application with working analytical workspaces | [Live app](https://loginexus-dashboard-preview.onrender.com/), [screenshots](../README.md#screenshots) |
| O05 | Tests and CI | Windows/Linux tests and API/dashboard container checks | [CI workflow](../.github/workflows/ci_pipeline.yml) |
| O06 | Orchestration and reproducibility | Ordered pipeline, staged outputs, failure propagation and documented reproduction | [Pipeline](../freight_intelligence/pipeline.py), [execution record](plano_finalizacao.md) |
| O07 | Forecasting | Compared baselines, validation-only selection, reserved observed tests and published metrics | [Method](temporal_evaluation.md), [all candidate scores](portfolio_evidence.md) |
| O08 | Optimization | Constrained solver, balance/capacity checks, infeasibility handling and scenario comparison | [Solver](transport_optimization.md), [planner](scenario_planner.md) |
| O09 | API | Documented read-only indicators, forecasts and analytical results, with optional authentication/roles | [API](api.md), [permissions](api_authentication.md) |
| O10 | Docker | Reproducible API/dashboard images, pinned runtimes and container validation | [Instructions](../README.md), [deployment files](../deployment/) |
| O11 | Continuous deployment | Publish the exact main revision only after required CI jobs succeed | [Workflow](../.github/workflows/ci_pipeline.yml), [policy](publicacao_continua.md) |
| O12 | Portfolio delivery | README, architecture/use guides, results, limitations, screenshots and recovery package | [README](../README.md), [static results](portfolio_evidence.md), [recovery](recovery.md) |

## Concrete expansions — 14 delivered items

Each row is delivered for its stated source population and period. It is not a
promise of complete national shipment coverage or unlimited future extensions.

| ID | Delivery and closed acceptance criterion | Evidence |
| --- | --- | --- |
| E01 | English default and optional Portuguese controls/core notices; stable internal/export identifiers | [Dashboard guide](dashboard.md) |
| E02 | Five-mode Brazilian atlas with 145 separately scoped annual indicators; detailed federal-concession railway observations, 2006–2025 | [Modal contracts](brazil_modes.md), [rail coverage](brasil.md) |
| E03 | Hosted public read-only API; public snapshots isolated from private plans; protected deployment permissions retained | [Public API](https://loginexus-dashboard-preview.onrender.com/api/docs), [guide](api.md) |
| E04 | Separate car-reference and truck-aware engines; explicit truck profile, reviewed saved geometry and GeoJSON | [Truck routing](truck_routing.md) |
| E05 | Road: 28 panel months, July 2024–October 2026, N/S components and partial-year flags; 775 paired 2025 state flows reconciled by origin and destination; archived yearbook separate | [History](brazil_road_history.md), [state pairs](brazil_road_od.md) |
| E06 | Cabotage: 510 observed links covering all 98 origins/71 destinations in the reviewed 2025 table, plus 21 original regional shares; no pairs inferred from marginals | [Port pairs](brazil_water_ports.md), [regional shares](brazil_water.md) |
| E07 | Port history: 62 original monthly observations, January 2021–February 2026; all period headlines reconciled and 2025 one-tonne rounding difference explained | [Monthly exports](brazil_water_history.md) |
| E08 | Inland transport: 62 monthly totals and three navigation components; 117 source cargo categories in 2025; eight dash quantities remain null and 46 explicit zeros remain zero | [Inland contract](brazil_inland.md) |
| E09 | Gas: 600 monthly operator/direction observations, 2021–2025; verified units, signed values, duplicate policy and missing-cell diagnostics | [Gas history](brazil_gas_history.md) |
| E10 | Air: 624 monthly aggregates, 36,860 recent monthly airport pairs and 1,102 source codes; paid/free/mail separated | [Air coverage](brazil_air.md) |
| E11 | Additional forecasting: evaluated railway, ANAC paid-stage, port-handling and Transpetro oil/product baselines; all candidate scores, source cutoffs and reserved tests | [Scores](portfolio_evidence.md), [vintage reports](brazil_modal_forecasts.md) |
| E12 | Scheduled auditing: 60 ANP monthly reports, 2021–2025, pinned 2021 unit dictionary and separate ANTT PDF revision detection; unreviewed revisions cannot replace serving data | [Policy](source_refresh.md), [five-year run](https://github.com/DiegoTDDD/freight-intelligence/actions/runs/44616465030) |
| E13 | Host-independent review: twelve English-interface screenshots, generated static results, public CSV and source evidence usable while the demo sleeps | [Screenshots](../README.md#screenshots), [static evidence](portfolio_evidence.md) |
| E14 | Verified recovery archives and pinned runtime; six-session/eighteen-render memory regression check without OOM | [Recovery](recovery.md), [CI evidence](https://github.com/DiegoTDDD/freight-intelligence/actions/runs/44656414891) |

## Outstanding requirements — explicitly not delivered

These requirements remain visible rather than being called completed. They are
distinct from the closed deliverables above. Each has a concrete completion test
and dependency; “more data” or “more quality” alone is not an acceptance criterion.

| ID | Requirement not delivered | Concrete completion criterion | Current dependency |
| --- | --- | --- | --- |
| X01 | Commercial truck dispatch assurance | Identified operating region/vehicle population, validated current restrictions, provider terms and operational acceptance evidence | No operating validation dataset or contracted dispatch assurance supplied; the routing demonstration is not certification |
| X02 | Toll and driver-hours compliance | Specified jurisdiction/rules, maintained tariff/duty inputs, implemented calculations and reviewed operating cases | No reviewed tariff/duty dataset or operating rules selected; calculations are not implemented |
| X03 | Independent API hosting and production availability | Separate API deployment at a selected destination, verified permissions, monitoring/recovery checks and an explicit availability target | Images and permission controls exist; the public API shares the free dashboard service. Independent hosting and an availability contract are not delivered |
| X04 | Measured optimization of a real company operation | Verified demand, capacities and costs; reproducible solved case; comparison with realized outcomes | Real operating records/outcomes not supplied. Synthetic examples are not measured savings |
| X05 | Additional geographic/source coverage beyond E02/E05–E10 | Name a source, population, period and unit contract; acquire evidence; implement, reconcile and publish the derived view through CI | No further reviewed source contract attached to this baseline. Earlier years, finer road geography, other OD populations, railway/pipeline operators and deduplication identifiers remain unacquired |
| X06 | Revision auditing of additional providers | Name a source/version population; implement bounded retrieval/comparison; retain proof of unchanged, changed and failure behavior | ANP and the ANTT PDF are delivered in E12. Other providers lack an approved retrieval/validation contract and implemented audit |
| X07 | Forecasts for additional target measures | Name target, unit and cutoff; obtain sufficient compatible history; compare baselines and score reserved observations | Other targets lack a reviewed sufficient history. Five full inland/port-export years do not satisfy the existing minimum-eight-year annual training protocol |

No paid service was purchased. Free hosting/provider limits, source revisions,
statistical overlap and missing inputs remain documented limitations. Paused local
hourly automation is separate from repository source-audit schedules.

## Verification baseline

Functional revision [05ba893](https://github.com/DiegoTDDD/freight-intelligence/commit/05ba893333578e6a2291886e606a56616443dc1f):
**474 lightweight tests passed on Windows and Linux**, all five CI/deployment jobs
succeeded, and the published inland API matched all four reviewed tables and source
hashes. The hosted six-session/eighteen-render check peaked at **249.9 MiB**, without
OOM. [Immutable run](https://github.com/DiegoTDDD/freight-intelligence/actions/runs/44656414891).
This is dated evidence, not a guarantee against future failures. Subsequent code
changes must pass their own CI; routine documentation/small-snapshot changes do
not rerun the large FAF pipeline.

## Change rule

Future updates must name the checklist ID, exact changed coverage and evidence.
Close a new source population as a separate delivery when its criterion is met.
Do not reopen E05 because an earlier road year might exist, E08 because another
inland dataset might exist, or E12 because another provider could be monitored.
An X requirement closes only after its stated outcome is demonstrated; it is
never removed just to report zero remaining work.
