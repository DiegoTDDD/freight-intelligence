# Transport scenario optimization

The first optimization milestone is a continuous minimum-cost flow model. It allocates divisible freight across a supplied directed network while satisfying every node's balance and each arc's capacity. It is independent of the heavy FAF pipeline.

```bash
python -m freight_intelligence.optimization.transport --scenario docs/examples/transport_scenario.json
```

SciPy is declared as a direct project dependency and its HiGHS solver is used. [SciPy's linear programming documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html) describes the equality constraints, variable bounds and solver status used here.

## Scenario contract

The JSON object requires `name`, `flow_unit`, `cost_unit`, `nodes` and `arcs`. Names and identifiers must be nonempty strings. Use a consistent flow unit and time period throughout the scenario; `unit_cost` is expressed as `cost_unit` per `flow_unit`.

| Element | Required fields | Meaning |
| --- | --- | --- |
| Node | `id`, `balance` | Positive balance supplies freight, negative balance demands freight, zero permits transshipment |
| Arc | `id`, `origin`, `destination`, `capacity`, `unit_cost` | Directed connection with finite nonnegative capacity and cost |

Node IDs and arc IDs must be unique within their lists. Endpoints must be distinct declared nodes. Total supply must equal total demand within an absolute tolerance of `1e-8`. All numeric fields must be finite JSON numbers; booleans and numeric strings are rejected. Zero-capacity arcs are allowed. Parallel arcs with distinct IDs can represent alternatives with different costs and capacities.

The objective is `sum(flow * unit_cost)` and the constraint at every node is `outgoing - incoming = balance`. No supply or demand is silently discarded. Negative costs are not supported. The solver has a 30-second time limit; a timeout or other nonoptimal termination is reported as a failure rather than as a certified optimum. Capacity/connectivity infeasibility returns a clear error and a nonzero command exit status.

## Example and output

The committed example is entirely synthetic. It has two supply nodes with 80 and 20 units, two demand nodes requiring 50 each, and four connecting arcs. Its optimum sends 50 on `a-x`, 30 on `a-y`, zero on `b-x`, and 20 on `b-y`, for a cost of 190 synthetic cost units. These are teaching values, not estimated FAF operating costs or demonstrated savings.

Successful runs write to the ignored `artifacts/optimization/transport/` directory, or the explicit `--output-dir`:

| File | Contents |
| --- | --- |
| `allocation.parquet` | Flow, capacity, cost contribution and utilization per arc |
| `node_balances.parquet` | Required balance, computed net outflow and residual per node |
| `summary.json` | Certified status, objective cost, units, interpretation, source SHA-256 and library versions |

Balance residuals and capacity violations are checked within an absolute tolerance of `1e-7` before writing. Utilization is null for zero-capacity arcs. Successful runs replace the files in the selected output directory; failed runs do not replace previous results, whose source hash remains in their summary. Input scenarios and all FAF layers are preserved.

## Scope and next routing milestone

FAF corridor volumes alone do not supply route costs, available capacity, vehicle constraints, transit times or a routable road network. The optimizer therefore requires those assumptions explicitly rather than deriving invented costs from volumes. It is not a road itinerary, vehicle scheduling model, multicommodity model or operational deployment recommendation. Supplies may be split across arcs and optimal allocations may not be unique.

To move to operational routing, provide a versioned network and cost/capacity assumptions, specify the planning period and units, and add vehicle/commodity/time constraints as required. Historical observed allocations would also be needed for defensible savings comparisons.

## Explaining common infeasible scenarios

Before optimization, the solver checks necessary local capacities: a supplying node needs
at least its balance in outgoing capacity, and a demanding node needs its demand in incoming
capacity. Failures identify the node, required flow, direction and available capacity in the
supplied units. A directed traversal over positive-capacity links also detects demand nodes
that cannot be reached from any supplier, including disconnected demand cycles.

These checks explain common problems but are not a complete feasibility certificate:
shared bottlenecks or other cut constraints can still make a scenario infeasible. HiGHS
remains the final solver and no partial allocation is returned for an infeasible network.
Planner errors use these explanations without saving or replacing any allocation.
