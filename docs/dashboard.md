# Local visual dashboard

Run the dashboard from the project's Python environment:

```bash
python -m pip install -e ".[app,dev]"
python -m streamlit run dashboards/app.py --server.address 127.0.0.1 --server.port 8501
```

Open `http://127.0.0.1:8501`. The **Workspace** selector in the sidebar provides five views. On narrow screens, open the sidebar using the arrow at the upper left.

| View | Contents |
| --- | --- |
| Freight analytics | Existing Gold indicators, commodity analyses and freight corridors |
| Scenario extrapolations | Published FAF scenario and saved extension chart, selected baseline, holdout comparison and CSV download |
| Temporal evaluation | Rolling validation/final-test score comparison, selected baseline, origin/target details and CSV download |
| Transport plan | Saved objective, units, allocation chart, origin/destination filters, capacity utilization, balance checks and CSV download |
| Scenario planner | JSON import, editable network, explicit simulation, reference/candidate comparison and downloadable result bundles |

The scenario view explicitly distinguishes the published FAF values (which include projections) from the saved extrapolation. Holdout scores measure agreement with FAF scenario points, not observed future demand. Its reader checks the input SHA-256 against the current annual Gold file and rejects stale projections.

The temporal evaluation view reads the separate saved report. Choose a metric and validation/test phase to compare errors and coverage. The selected baseline is always the one chosen using validation only, even when viewing the final test. The prediction table exposes origin year, target year and actual calendar horizon. The same report validator is used by the API, and opening the view does not train or change any model. A missing report has a friendly unavailable state.

The transport view reuses the API's result validator. Its units and scenario name remain visible, including the synthetic teaching-example label. Filters affect the displayed links and download; the cost/supply cards always describe the complete saved scenario. The table is capped at 1,000 matches and the chart at 20 links; CSV includes every matching link. The node table shows saved conservation checks.

Saved-result workspaces read only their needed files. Missing/invalid optional results show an explanatory state instead of blocking unrelated views. Changes to file timestamps/sizes invalidate bounded caches, which also expire after 30 seconds. Results refresh on the next interaction/rerun, not by continuous polling. These views do not run a pipeline, solver or model fitting. The separate [Scenario planner](scenario_planner.md) runs a bounded transport simulation only after explicit form submission, keeping results in session memory without replacing saved files.

Data paths resolve from the project root even when launched from a different working directory. `LOGINEXUS_DASHBOARD_DATA_ROOT` can point to another result-tree root with the same `data/`, `models/` and `artifacts/` layout; this is also used for isolated UI tests.

This dashboard reads local files directly and is a separate loopback-only service from the API. The API's `X-API-Key` authentication does not protect Streamlit. A public dashboard deployment would need its own access controls. The Docker Compose API runtime remains API-only; the local dashboard runs in the Python environment with the application extra installed.

Automated UI tests use `streamlit.testing.v1.AppTest` with temporary data to exercise navigation, filters, empty results, missing/corrupt outputs and cache invalidation without requiring full FAF ingestion.

The `Historical observations` workspace also supports session-only evaluation of an uploaded
or pasted annual series with an explicit source manifest. See
[historical evaluation](historical_evaluation.md) for the input contract and limitations.

### Reading the historical charts

The historical workspace filters results by metric, keeping each metric's units separate.
The summary cards always report the validation-selected model on the reserved final test.
The window and comparison-model controls change only the charts, not model selection or
the downloadable report. Supplied values and predictions are plotted at their target years;
validation uses expanding training prefixes, while test predictions use a fixed origin.
Absolute-error bars show the difference in the chosen metric's units. A missing model/window
combination has an explicit empty state. WAPE is unavailable when actual values sum to zero.

The historical form supports an optional forecast horizon from zero to ten years. A nonzero
horizon adds a separate forecast chart/table after the evaluation and includes `forecast.csv`
in the same download. The forecast uses the validation-selected model refit on all supplied
points. The history and forecast have distinct chart series; results use each metric's units.
Zero keeps an evaluation-only result and removes forecasts on the next submission.

## Opening the dashboard on Windows

Double-click `Abrir LogiNexus.cmd` in the repository folder. It uses the project's `.venv`
when available, otherwise the existing `miniconda3/envs/freight-intelligence` environment.
Set `LOGINEXUS_PYTHON` to the full Python executable path for another installation.
No packages are installed automatically and no pipeline is run.

The launcher reuses a responding Streamlit service on port 8501. If the port is occupied
by a nonresponding/different service it reports an error instead of killing that process.
When starting the dashboard, it binds to 127.0.0.1, waits for the health endpoint and then
opens the browser. Startup errors go to `logs/dashboard.log`, which is excluded from Git.
The launcher can also be called with `python -m freight_intelligence.launch_dashboard`;
`--no-browser` allows a terminal-only check and `--port` chooses another local port.

The panel is a local process. Restarting Windows or stopping Python can make it unavailable;
opening the launcher starts it again. This does not install an automatic Windows startup
service, alter firewall settings, expose a public server, or automatically restart crashes.
A responding health endpoint confirms the server, not every dataset's availability.
