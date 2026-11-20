# Read-only API

## Hosted entry point

The hosting image serves the dashboard at `/` and an independent HTTP API at
`/api`, with interactive documentation at `/api/docs` and the machine-readable
contract at `/api/openapi.json`. These share one hosting process and its free-tier
availability limits; this is not a separate server or an availability guarantee.

The hosted API reads only the reviewed `deployment/preview_data` snapshot (or the
explicit `LOGINEXUS_DASHBOARD_DATA_ROOT`). Every optional reader is pinned to that
root, so saved plans elsewhere in the project cannot become public accidentally.
The published snapshot contains annual indicators, scenario extrapolations and
their temporal evaluation. Transport plans are not bundled and return HTTP 503.
There are no write, upload, training or optimization endpoints.

Authentication settings remain effective on the mounted API. In the public-data
deployment, anonymous reads are intentional; never place private data in the
public snapshot. The container check exercises both the dashboard and the real
API HTTP server without network access, within 512 MiB and on a read-only filesystem.

## Local standalone server

Install and start from the project environment:

```bash
python -m pip install -e ".[api,dev]"
python -m uvicorn freight_intelligence.api.app:app --host 127.0.0.1 --port 8000
```

Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Process liveness; does not require datasets |
| `GET /ready` | Checks that the annual Gold KPI dataset is readable with required columns |
| `GET /annual-kpis` | Annual Gold rows, optionally filtered by `metric_type`, `start_year`, `end_year` |
| `GET /annual-forecast` | Saved scenario extrapolations, optionally filtered by `metric_type` |
| `GET /brazil/indicators` | Scoped indicators for road, rail, water, air and pipelines, filtered by `mode`, `start_year`, `end_year`; includes unit, scope, sources and quality notes |
| `GET /brazil/gas-movements` | ANP 2025 monthly realized point volumes, filtered by `month`, `point_type` (receipt/delivery) and `operator_id`; retains observed/missing counts and source units |
| `GET /brazil/water-freight` | ANTAQ navigation/cargo/regional references, filtered by `dataset`, `year` and `direction`; tonnes and TEU retained separately |
| `GET /transport-plan` | Saved allocation, filtered by `origin`, `destination`, `active_only` |
| `GET /transport-plan/nodes` | Saved node balances and conservation checks |
| `GET /temporal-evaluation` | Temporal baseline scores, filtered by `metric_type` and `phase` |
| `GET /temporal-evaluation/predictions` | Origin/target predictions with filters and pagination |

Metrics are `tons`, `value`, and `tmiles`. Results are sorted by metric and year. Unknown metrics, invalid years and reversed year ranges return HTTP 422. Valid filters with no matching rows return an empty data list. Missing or unreadable datasets return HTTP 503 without exposing local file paths.

The API never launches the pipeline, fits a model or runs an optimizer. It reads existing outputs. Forecasts and transport results are optional: annual indicators and readiness remain available when they have not been generated. Run `python -m freight_intelligence.ml.annual_forecast` separately to prepare forecasts.

## Saved temporal evaluation

Generate the report separately with `python -m freight_intelligence.ml.temporal_evaluation`. The endpoints read `artifacts/evaluation/annual/` and verify its source SHA-256 against the current annual Gold table. They validate phase boundaries, reference values, error calculations, score coverage, aggregate metrics and consistency of selection with validation MAE. Missing, stale or inconsistent reports return HTTP 503; the API does not run evaluation or replace forecasts.

`phase` accepts `validation` or `test`. The predictions endpoint also supports `selected_only`, `limit` (1–1000, default 100) and nonnegative `offset`. Its `total` counts filtered rows and `count` counts the returned page. Sorting is deterministic by metric, phase, baseline, origin and target year. Public metadata includes the split parameters, source hash, interpretation and validation-selected models, excluding private paths. These data routes use the same optional `X-API-Key` protection as the other analytical endpoints.

## Saved transport results

Generate an explicit scenario separately, for example:

```bash
python -m freight_intelligence.optimization.transport --scenario docs/examples/transport_scenario.json
```

The bundled example is synthetic. These endpoints read `artifacts/optimization/transport/`. Every request validates the complete bundle (`summary.json`, `allocation.parquet`, `node_balances.parquet`) before filtering. Checks cover finite values, unique IDs, endpoints, capacities, arc costs, utilization, flow conservation and consistency with the saved objective and total supply. Missing, malformed or inconsistent results return HTTP 503. Concurrent replacement of files can temporarily return 503 until the bundle is consistent again.

Both endpoints accept `limit` (1–1000, default 100) and `offset` (zero or greater). Responses contain `count` for the page, `total` for all matching rows, `limit`, `offset`, `data`, and a public `summary`. Arcs sort by `arc_id`; nodes sort by `node_id`. Filters match exact node IDs. `active_only=true` excludes flows at or below `1e-7`. Unknown node IDs and offsets past the last row return empty pages.

The summary exposes scenario name, certified status, units, cost/supply totals, interpretation and input SHA-256. Private source paths and unrelated metadata are omitted. Queries never recalculate or change the solution. Outputs remain scenario allocations rather than road itineraries or claims of measured savings.

The default data locations resolve from the package's project root. Tests inject temporary directories through `create_app(gold_dir=..., model_dir=..., transport_dir=...)`; importing the API does not read or create datasets. Responses retain source units and label the projected scenario values explicitly.

The standalone command binds to loopback. Optional [API-key authentication](api_authentication.md) protects all data endpoints when configured, including when mounted under `/api`. Per-user permissions are also supported; hosting uses the snapshot isolation described above.

### Forecast freshness and consistency

`/annual-forecast` validates the full saved projection bundle before returning any rows:
its metadata must match the current annual Gold SHA-256, its baseline selection must agree
with forecast model names, and projected years must be unique and after the source years.
Missing evaluation/metadata, a changed Gold file or inconsistent rows return HTTP 503.
The dashboard and API now share this validation. Annual indicators and readiness remain
independent of forecast availability. Regenerate and validate the small annual forecast
bundle when the annual Gold changes; this does not require running the full pipeline.

## Regional road flows

`GET /api/brazil/inland-transport` serves separate inland-waterway transport
observations. Views: `monthly` (62 months, totals plus three navigation components),
`annual` (six observed-period totals), `navigation` (three 2025 source totals),
`commodities` (117 categories; eight null quantities and 46 explicit zeros retained).
Filters: `year=2021..2026` (2025 only for detail views), `month` (monthly only),
exact `commodity` label (commodity view only). `limit=1..500`, `offset>=0`.
Shares retain the full source denominator. [Scope and original evidence](brazil_inland.md).

`GET /api/brazil/water-history` serves 62 original numeric monthly port-handling
observations, January 2021–February 2026. `view=annual` returns six observed-period
totals with completeness and rounding residuals. Filters: `year=2021..2026`,
`month=1..12` (monthly view only). `limit=1..500`, `offset>=0`. 2026 is partial;
missing months return no rows. [Original exports and interpretation](brazil_water_history.md).

`GET /api/brazil/road-state-pairs` serves 775 reviewed 2025 UF→UF pairs, including
EX/exterior and both account categories. Origin and destination margins independently
reconcile to 1,368,627,704 integer tonnes. Filters: `origin_state`,
`destination_state`, `same_state`; year is restricted to 2025. Pagination:
`limit=1..500` (default 100), `offset>=0`. `filtered_tonnes` covers all matching
rows, not only the returned page. [Source contract and interpretation](brazil_road_od.md).

`GET /api/brazil/road-history` serves the separately reviewed 28-month panel
window, July 2024–October 2026: 56 N/S account-category rows containing tonnes
and document counts. Views: `monthly` (default), `annual` (component/subtotal
rows with completeness flags), `editions` (twelve 2025 source comparisons).
Optional filters: `year=2024..2026`, `account_type=non_own_account|own_account`.
`account_type=all` is accepted only for annual subtotals; omit it for both monthly
categories. Pagination uses `limit` (1–500, default 100) and zero-based `offset`.
Partial years are not annualized; MDF-e documents are not unique trips.
[Source capture, units and edition comparison](brazil_road_history.md).

`GET /api/brazil/road-flows` serves 16 reviewed ANTT RGI flows for 2025.
Filter with `origin_state=PA&destination_state=MT&same_region=false`.
These are selected regional cargo movements, not operational road itineraries.
See [scope and source quality](brazil_road.md).

`GET /api/brazil/road-monthly?month=1` returns the published January total and
the annual reconciliation, explicitly calculated from all 12 months. Omit the
month filter for the complete 2025 monthly table. Invalid months return 422;
missing or inconsistent monthly data returns 503. Analytics permissions apply.

## Airport freight and observed-subtotal forecasts

`GET /api/brazil/air-freight?view=pairs&year=2025&origin=SBGR` exposes reviewed
ANAC airport-pair stages. Views include monthly/annual aggregates, pairs, airport
reference data, forecast values and evaluation scores. Pagination is bounded to
1000 rows per page. Paid/free/mail remain separate and missing fields are counted.
See [coverage, forecast evaluation and filters](brazil_air.md).

## Historical gas and diagnostics

`GET /brazil/water-pairs` exposes 21 paired regional cabotage fractions for 2025.
Optional `origin_region` and `destination_region` filter source labels; fractions
retain the full-panel denominator. They are not absolute tonnes or port routes.
The hosted path is `/api/brazil/water-pairs`; missing/invalid snapshots return 503.

`GET /brazil/modal-forecasts` exposes port-handling and Transpetro oil/product
vintage reports. `mode=water|pipeline`, `view=scores|predictions|forecast`, optional
`phase` (scores/predictions) and `year` (predictions/forecast), plus bounded
pagination are supported. These forecasts retain a 2024 cutoff; they are not
current observations. [Source, protocol and units](brazil_modal_forecasts.md).

The gas endpoint accepts years 2021–2025 (`year=2025` is the default). Add
`include_diagnostics=true` for source point/date groups, with
`diagnostics_limit` up to 500 and `diagnostics_offset`. Normal responses omit large
diagnostic arrays. See [historical quality rules and investigated absences](brazil_gas_history.md).

### Observed cabotage port pairs

`GET /api/brazil/water-port-pairs` returns 510 reviewed 2025 links covering all 98 source origins and 71 destinations.
Exact optional filters: `origin_port`, `destination_port`; `year=2025` only.
Pagination: `limit` (1–500, default 100), `offset` (zero-based). `filtered_tonnes`
and `total` apply before pagination. Reviewed population coverage and original source
context are explicit in metadata. Analytics permission is required in authenticated
mode. See [scope and examples](brazil_water_ports.md).

### ANAC forecast target measures

The air endpoint also exposes `view=predictions` for the portable report's
validation/test predictions. For `forecast`, `scores` and `predictions`, select
`measure=paid_cargo_kg|free_cargo_kg|mail_kg`; paid cargo remains the default.
Use `nature=domestic|international` to keep statistical populations separate.
`phase=validation|test` applies only to scores/predictions; other combinations
return 422. The same pagination and analytics permissions apply.
All six targets use kg, 2010–2025 histories, validation through 2022 and reserved
2023–2025 tests. Forecast years 2026–2028 are point estimates. No model is trained
on request. [All results and limitations](brazil_air.md#forecast-evaluation).

## Dated trip cost and selected duty planning

`GET /api/brazil/trip-planning` exposes bounded, stateless calculations from the
reviewed Autoban tariff snapshot and selected daytime duty rules. It requires
analytics permission, stores no scenario and never authorizes dispatch.
[Parameters, limits, source dates and examples](trip_planning.md).

## Declared weekly duty review

`GET /api/brazil/duty-review` returns a published synthetic example.
`POST /api/brazil/duty-review` evaluates declared JSON without creating records;
this is a stateless calculation, not a mutable dataset endpoint. Both use analytics
permissions. The body is bounded at 64 KiB/300 events and ten seconds to receive.
[Schema, dates, examples and unsupported contexts](weekly_duty.md).
