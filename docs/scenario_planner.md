# Interactive transport scenario planner

Open the local dashboard at `http://127.0.0.1:8501` and select **Scenario planner** in the Workspace sidebar. The starting data is the explicitly labelled synthetic teaching example. No saved plan or FAF layer is used as an editable input.

1. Give the scenario a name and consistent flow/cost units.
2. Edit the node table: positive balance supplies freight, negative balance demands freight, and zero permits transshipment. Supply and demand totals must match.
3. Edit the directed-link table: IDs must be unique, endpoints must refer to declared nodes, and capacity/cost must be finite and nonnegative. Tables allow adding and deleting rows.
4. Click **Simulate scenario** to validate and solve the submitted inputs.

Form edits are submitted together; opening the page or editing a cell does not run the optimizer. Pressing Enter in the form does not submit it. The interactive path is capped at 100 nodes and 500 links, with the underlying solver's existing 30-second time limit. It computes divisible minimum-cost freight flows, not vehicle itineraries or schedules.

## Import and reuse a scenario

Expand **Import a scenario JSON** and select a `.json` file or paste its contents. Click **Load scenario** to apply it to the editors; selecting a file alone does not load it, and loading never invokes the solver. When both inputs are present, the selected file takes precedence. Click **Simulate scenario** separately after checking the imported tables.

Imports accept UTF-8 JSON (including a UTF-8 BOM), up to 256 KiB, with 1–100 nodes and 1–500 links. The contract uses exactly the fields documented in the [transport optimization guide](transport_optimization.md): unknown fields, duplicate JSON field names/IDs, malformed values, non-finite numbers, negative cost/capacity, invalid endpoints and unbalanced supply/demand are rejected. Scenario names are limited to 140 characters and flow/cost unit names to 100. Connectivity and capacity feasibility are checked when simulation is submitted.

An accepted import clears the prior editor changes and simulation result, then loads the new scenario for review. A rejected import preserves the current work and result. **Restore synthetic example** resets the editors and clears the previous simulation. The selected upload or pasted import buffer remains available; it is only applied again by clicking Load scenario.

To reuse a downloaded bundle, extract its `scenario.json` and import that file. The dashboard imports JSON, not the ZIP itself. Imported content is data only and is not executed or saved to the repository.

## Session result and download

The result below the form is labelled as the last successful submission. Editing inputs without submitting leaves that result unchanged. A failed new submission clears it and shows a validation/infeasibility message. Results live only in that browser session and can be lost on session reset; download the bundle to retain them. No scenario files, Gold tables, saved transport outputs or model reports are written by the planner.

**Download scenario and solution** produces a ZIP containing:

- `scenario.json`: the exact submitted input, suitable for the transport CLI.
- `summary.json`: solver status, objective, units, input SHA-256 and execution provenance.
- `allocation.parquet` and `allocation.csv`: optimized flows and capacity utilization.
- `node_balances.parquet` and `node_balances.csv`: conservation checks.

The summary's SHA-256 identifies the input bytes included in the same ZIP. Extract `scenario.json` and pass it to `python -m freight_intelligence.optimization.transport --scenario <path>` to reproduce the calculation. This download does not automatically publish a plan to the API or replace the dashboard's saved-plan view.

The default example costs 190 synthetic units. Reducing link `a-x` capacity from 50 to 40 changes the optimum to 240 synthetic units. These examples demonstrate constraints, not measured operating costs or savings. Supply/demand, network structure, units and costs for real planning must be supplied explicitly.

## Compare alternatives

After a successful simulation, click **Use this result as reference**. The reference is copied into session memory independently of the current result. Edit or import an alternative and simulate it: the panel then shows reference/candidate costs, absolute and relative cost change, and flow changes per directed link. The initial example compared with capacity 40 on `a-x` changes cost from 190 to 240, a difference of +50 (+26.32%).

Comparisons require exactly matching flow/cost unit labels and the same node IDs and supply/demand balances (absolute balance tolerance `1e-8`). The tool does not infer unit conversions or planning periods; provide compatible assumptions. Link IDs/endpoints may differ: removed links have zero candidate flow, added links have zero reference flow, and matching uses ID plus both endpoints. Relative cost change is unavailable when the reference cost is zero or the ratio cannot be represented as a finite number.

Importing a new input or restoring the example clears the current simulation but preserves the reference, so alternatives can be compared. **Clear comparison reference** discards the reference without changing the current result. Only one reference is retained. Neither comparison nor reference capture runs the solver; solving remains an explicit form action.

**Download comparison bundle** contains `comparison.json`, `flow_changes.csv`, and the complete scenario/solution files under `reference/` and `candidate/`. Input SHA-256 values identify the two scenarios. Retain the download before resetting the browser session. The reported cost difference is a model-based scenario difference, not measured operational savings; optimal flow allocations may be nonunique.

The planner remains part of the loopback-only local dashboard. API endpoints stay read-only and their authentication behavior is unchanged.
