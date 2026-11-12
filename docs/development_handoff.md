
## Development handoff — 2026-11-12

Repository: `C:\Users\Usuario\freight-intelligence`. Python environment:
`C:\Users\Usuario\miniconda3\envs\freight-intelligence\python.exe`.
Work remains uncommitted. Preserve all local changes. No commit, push, deploy or full
~100M-row pipeline without explicit authorization. Do not repeatedly ask to continue.

Completed: Windows commodity print fix; workflow failure propagation; API/container runtime;
scenario forecasts; transport solver/planner/import/comparison; temporal evaluation; historical
CSV/provenance reports and optional forecasts; historical dashboard charts; archived FAF5.5.1
2017–2021 estimate adapter and dashboard action. The archived Gold historical check has five
points per metric and only 2021 reserved for testing. Estimates are not direct measurements.

Current milestone: optional API users registry with hashed random tokens, independently
revocable users (restart required), and analytics/transport/evaluation permissions. Shared-key
and anonymous loopback modes retained. Running service configuration has not been changed.
Authentication tests: 28 passed. Small CSV examples were accidentally excluded by generic
CSV ignore rules; `docs/examples/*.csv` is now explicitly included.

Next useful steps: add repeatable container verification for the users-registry mode using
an ephemeral read-only registry mount; validate a fresh image before altering any running
service. Then choose a production configuration only once an actual hosting target and
identity requirements are known. Operational road routing still requires supplied road
network, vehicles and measured costs. Do not invent them or call scenario cost differences
measured savings. Prefer addressing these real limitations over adding more synthetic demos.

Read README and relevant docs for contracts; `docs/api_authentication.md` covers the registry.
Keep this handoff current after concrete milestones. Lightweight regression suite excludes
`tests/test_faf5.py`, which uses the large real dataset. Do not run that full-data test here.

Regression update: lightweight suite 232 passed, excluding only the full-data FAF test.
The container checker now covers a temporary read-only users registry as well. The Docker
engine was stopped during the first attempted build; Docker Desktop was started to retry.
If execution is interrupted, validate `docker info`, build `loginexus-api:users-check`, then
run `scripts/check_api_container.py --image loginexus-api:users-check`. Do not replace the
running Compose service without need. Git now includes the small example CSVs required by CI.

Container validation completed successfully: fresh image `loginexus-api:users-check` built,
38 pinned packages verified. Local mode, shared-key mode, per-user permission mode,
disabled-user rejection, read-only registry mount and mandatory-key startup refusal all
passed. Test containers and temporary registries were removed by the checker. No running
Compose service was replaced. The next milestone should assess production readiness
against an actual target, or improve historical source verification; do not rerun these
successful checks without a relevant code change.

### 2026-11-12 automatic continuation: mounted API permissions

Fixed individual-user permission resolution for APIs mounted under a URL prefix (for example
`/api`). Previously external path prefixes could cause transport/evaluation routes to inherit
the analytics permission. Resolution now uses the matched route with an explicit permission
map; unclassified protected routes deny individual-user access. Added mounted-app and
unknown-route regressions. Auth-focused suite: 30 passed; Ruff passed after import cleanup.
No service configuration, images, credentials or deployment changed. The existing verified
container image predates this source fix and would need rebuilding before deployment.

### 2026-11-12 automatic continuation: forecast freshness

Fixed `/annual-forecast` serving stale/mismatched saved forecasts. API and dashboard now
share `load_projection_files`, checking current Gold hash, required metadata/evaluation,
selected model consistency and future/unique years. Added source-change, missing-metadata,
invalid-selection and duplicate-year API regressions. Annual indicators remain independent.
Tests generate complete tiny forecast fixtures rather than isolated forecast Parquets.
No pipeline, service restart, image replacement, commit or push performed.

### 2026-11-12 automatic continuation: actionable infeasibility errors

Transport solver now identifies nodes with insufficient incoming/outgoing capacity and
unreachable demand components before optimization. Errors include the node and supplied
flow units. Positive-capacity reachability catches disconnected demand cycles. These are
necessary checks only; HiGHS still detects shared network bottlenecks and certifies results.
Added shortage-detail and disconnected-cycle regression cases. No partial solution, saved
plan or source scenario is changed by errors. No service restart or deployment performed.

### 2026-11-12 automatic continuation: non-executing pipeline plan

Added `python -m freight_intelligence.pipeline --plan [--skip-existing]`. It emits JSON
run/skip decisions, reasons, missing outputs and large-data flags without invoking any step.
Dependency rebuild propagation matches the existing execution policy. Seven orchestration
tests passed, including guarantees that no patched transformation is called in plan mode.
Ran only the preview against current local output existence and saved it to the chat's
outputs/pipeline-plan.json. This is not a full pipeline run; existing datasets are untouched.
The plan intentionally checks existence only, not file/source freshness.

### 2026-11-12 automatic continuation: Windows/Linux regression CI

Expanded lightweight CI to a Windows/Ubuntu matrix with Python 3.13, Ruff enforcement,
20-minute per-job timeout and separate retained JUnit reports. Failure on one OS no longer
cancels the other. This addresses platform-specific failures such as the original Windows
cp1252 issue rather than relying only on Ubuntu. Docker remains Linux-only and full FAF
data tests remain excluded. No remote workflow has run: changes are uncommitted/unpushed.

### 2026-11-12 automatic continuation: downstream Windows console failures

Found two remaining Polars preview prints in commodity_growth and commodity_share_change.
These would reproduce the original cp1252 crash later in the pipeline after commodity lookup
was fixed. Removed only those display calls; Parquet content and summary logs remain.
Added isolated tests using strict cp1252 stdout and Unicode commodity names, verifying growth
and share calculations as well as preserved Unicode output. Ten related tests passed and
Ruff passed. No full pipeline run or real Gold rewrite was performed. This is a completion
of the original Windows failure investigation, not a request to reprocess large data.

### 2026-11-12 automatic continuation: preserve completed Bronze/Silver on failure

Bronze and Silver streaming sinks now write to a uniquely named same-directory temporary
Parquet and atomically replace the published path after success. Normal exceptions remove
the temporary file, leaving the previous output intact; a failed first write publishes no
output. This prevents a partial newly written file from being treated as reusable merely
because the published path exists. Staging is on the same filesystem, with no in-memory
copy. It may require old+new output disk space; hard kills may leave hidden staging files.
Tested failure preservation for both layers and an actual two-row Bronze Parquet write,
plus orchestration tests. No real datasets were rewritten or full pipeline run performed.

### 2026-11-12 automatic continuation: optional users-registry Compose setup

Added compose.users.yaml: mandatory auth, empty shared-key setting, required private host
registry path and read-only bind mount with no automatic host-directory creation. The base
loopback binding and restricted filesystem remain. Added scripts/check_users_compose.py
and executed it successfully: missing variable rejected, merged auth/mount/runtime settings
verified. It starts no service and saves no working credentials. Default Compose untouched.
This closes the configuration gap for users who choose individual API keys locally.

### 2026-11-12 automatic continuation: interval-aware growth and undefined rates

Annual growth now adds previous_year, elapsed_years and annualized_growth_rate while keeping
existing growth_rate as the interval change. Zero denominators become null rather than inf;
CAGR for a single year/zero start is null. Annual input validation rejects duplicate
metric/year pairs, nulls and invalid totals before writing. Thirteen annual/orchestration
tests passed and Ruff passed. Validated only temporary fixtures; real Gold remains unchanged.
Dashboard already describes interval growth, and existing saved data contracts stay valid
because added fields are optional to existing readers. No full pipeline executed.

### 2026-11-12 automatic continuation: supplied-road-graph routing component

Implemented a separate minimum-cost path command for a supplied directed road graph and
one supplied vehicle. Explicit weight/height/closure restrictions filter edges; supplied
per-km costs and tolls determine path cost. No maps or real operating values are invented.
The bounded input and exclusive JSON output include source/input hash and route edges.
Eight targeted tests cover detours, direction, limits/closures, missing declarations,
zero-length origin/destination and CLI overwrite refusal. This is groundwork only:
operational deployment still requires a verified road network and broader vehicle/routing
requirements. No claim of a driving itinerary. See docs/road_routing.md. No API/UI changes.

### 2026-11-12 automatic continuation: supplied-road route dashboard

Added Supplied road route workspace with file/paste input, explicit calculation, source and
vehicle identification, ordered route, cost/distance/exclusion metrics and JSON download.
No preloaded graph, automatic map requests, saved server file or solver API endpoint.
Failed submissions clear stale routes. Dashboard/routing suite: 24 passed, Ruff passed.
Browser-verified a clearly synthetic test (5 km, 17 test cost units) and downloaded result.
The dashboard had stopped; restarted only its loopback process, now listening on port 8501.
Screenshot: chat outputs/loginexus-rede-viaria-painel.png. No real itinerary was generated.

### 2026-11-12 automatic continuation: consolidated integration milestone

Full lightweight suite after the recent feature changes: 265 passed; Ruff passed. Built a
fresh independent loginexus-api:validated image, verified 38 runtime pins, and successfully
checked anonymous/shared-key/individual-user modes, disabled credentials, permissions,
read-only registry and refusal without mandatory credentials. Compose merge checker also
passed. Test containers removed; no existing service replaced. See docs/current_status.md
for a compact feature inventory and real external prerequisites. Avoid repeating these
successful checks without relevant code changes; do not invent new demos to fill check-ins.

### 2026-11-12 user continuation: reliable dashboard launcher

Added root Abrir LogiNexus.cmd and freight_intelligence.launch_dashboard. Detects existing
project .venv/known Conda environment (or explicit LOGINEXUS_PYTHON), reuses a healthy local
Streamlit service, refuses occupied nonhealthy ports and starts a detached loopback server
with logs. No pipeline or package installation. Browser opens only after health succeeds.
Seven tests passed, Ruff passed. Real startup verified on temporary port 18501, health ok;
only that verified temporary process was stopped afterwards. Existing 8501 service was
successfully reused and left running. No Windows autorun service or restart daemon added.

### 2026-11-12 user continuation: per-link route explanation

Added ordered per-link cost/distance/toll breakdown and all applicable exclusion reasons.
Dashboard displays the detail table; JSON download includes the same values. Twenty-six
routing/dashboard tests passed and Ruff passed. Browser verified a synthetic restricted
network: direct link excluded by weight+height; selected detour totals 4 km and 9 test units.
Downloaded JSON verified against totals and exclusion reasons. Restarted only the known
local dashboard through the new launcher to load updated code; no data pipeline executed.

### 2026-11-12 user continuation: review-only HTTPS deployment draft

Added compose.production.yaml, deployment/Caddyfile and check_production_config.py (also
wired into CI). Requires explicit domain/private users registry, mandatory individual-key
auth, clears shared key, removes API host ports with !reset, and uses internal backend.
Pinned official Caddy proxy image at verified digest; default host bindings are loopback.
Validated Compose merge and missing-domain refusal. Parsed Caddyfile using the pinned
image in a disposable container with --network none and no published ports: HTTPS host,
api:8000 upstream and disabled admin confirmed. No service started, certificates requested,
DNS/firewall changed or public deployment performed. See docs/deployment.md for prerequisites.
Ruff and diff checks passed. Real host/domain/identity choices remain pending.

### 2026-11-12 user continuation: proxy/API runtime integration

Added scripts/check_proxy_runtime.py and CI invocation. Verified actual HTTP forwarding
through pinned Caddy to the authenticated API, 401 for absent/invalid keys, 403 across
permission boundaries, allowed requests reaching ordinary empty-data 503 responses,
public health/docs and no API host-published port. Temporary proxy uses an edge bridge
plus internal backend like the deployment draft; Docker does not publish ports on an
internal-only network. All temporary containers and both networks are removed afterwards.
Actual integration passed against loginexus-api:validated; Ruff/diff checks passed.
HTTP is deliberately loopback-only: no TLS certificate or external hostname is claimed.
Asked the user whether a real domain/server exists; no deployment/contract/push is authorized.

### 2026-11-12 owner clarification: no existing infrastructure

Owner has no domain/server and expects the implementation to include infrastructure
preparation. Do not require them to provision a VPS/domain as an unexplained prerequisite.
Prepared render.yaml for a Free API preview with provider subdomain/TLS, mandatory generated
shared API key, no paid resources and auto-deploy off. Validated against Render's official
JSON schema fetched over HTTPS. Docs/free_preview.md states limits and that current Docker
image has no bundled analytics data, so this is API preview readiness, not a complete hosted
Streamlit app. No account/service, commit/push or cloud deployment created. Account ownership,
terms/payment and explicit publication approvals remain user steps at the actual boundary.
Sites connector supports static/Worker outputs, not the existing Python Streamlit/HiGHS
runtime, so no misleading static replacement was created. Continue source/data packaging
for a useful hosted app before asking the user to approve an initial deployment.

### 2026-11-12 Render login and complete dashboard preparation

Confirmed Render login in the browser; no service was created. The account does not yet
have a Git provider connection; a public-repository source can avoid granting additional
GitHub account access after the reviewed source is pushed. Original no-commit/no-push rule
still applies until explicit authorization. Do not deploy the old remote revision.

Prepared full dashboard image and separate Free Blueprint deployment/render.dashboard.yaml.
Generated an 18-file, roughly 8.6 MB allowlisted public-FAF snapshot with hashes, no raw/Silver,
credentials or saved transport scenarios. Optional forecasts/temporal reports were validated;
absolute local input metadata paths removed. Snapshot is in deployment/preview_data and
explicitly trackable for the reviewed preview. Image runs as non-root with HOME=/tmp.
Dashboard views passed inside a read-only, network-isolated 512 MiB Linux container.
Separate dashboard lock (59 packages) resolves Streamlit compatibility: pyarrow 25.0.1 and
websockets 16.x, while API runtime lock is unchanged. Blueprint passed official Render schema.
Snapshot and runtime-lock tests: 14 passed. Final pinned image rebuild pending completion.

Final dashboard image verification completed: 59 locked runtime packages match installed
versions, and analytical/forecast/temporal views passed inside a read-only network-isolated
512 MiB Linux container. Full lightweight suite now 276 passed; Ruff passed. Final source
publication requires explicit authorization for commit/push to DiegoTDDD/freight-intelligence.
No Git staging, commit, push or Render service creation has occurred. Owner is logged into
Render; use the dashboard-specific blueprint, not the earlier empty-data API-only draft.
