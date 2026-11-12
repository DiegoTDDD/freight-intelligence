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
