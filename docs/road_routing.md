# Routing on a supplied road graph

`freight_intelligence.optimization.road_routing` provides the next building block beyond
divisible transport allocation: a directed minimum-cost path for one explicitly described
vehicle. It does not download maps, infer missing limits, estimate operating costs from FAF,
or provide a verified driving itinerary. An actual road dataset is still required before
this can support an operational use case. No production routing integration is claimed.

```bash
python -m freight_intelligence.optimization.road_routing --input request.json --output route.json
```

The input JSON requires `network`, `vehicle`, `origin` and `destination`:

| Object | Required fields |
| --- | --- |
| Network | `source` (source identification), `cost_unit` (one consistent currency/unit), `nodes` (unique string ids), `edges` |
| Edge | `id`, `origin`, `destination`, `distance_km`, `toll`, `max_gross_weight_t`, `max_height_m`, `closed` |
| Vehicle | `id`, `gross_weight_t`, `height_m`, `cost_per_km` |

Gross weights use metric tonnes and heights metres. Every edge must declare positive distance
and limits, a nonnegative toll, and an explicit boolean closure flag. Missing restrictions
are not assumed unrestricted. All numerical values must be finite JSON numbers; booleans
are rejected as numbers. Gross vehicle weight includes its load. The vehicle's per-kilometre
cost and tolls must share the declared cost unit. Costs are supplied assumptions, not measured
savings. Directed reverse travel requires a separately supplied reverse edge. Parallel links
with distinct ids are supported.

Edges are excluded when closed or when declared vehicle weight/height exceeds their limit.
The route minimizes `distance_km * cost_per_km + toll`; equal costs prefer shorter distance.
Dijkstra's algorithm is valid because every accepted edge cost is nonnegative. The result
identifies ordered nodes/edges, distance, total cost, excluded edge ids, source and original
input SHA-256. Unreachable destinations fail without writing a partial route. Identical
origin/destination yields a zero-cost empty edge path. Existing output files are rejected.
Input is bounded to 8 MiB, 10,000 nodes and 50,000 edges.

The component does not cover turn restrictions, axle limits, hazardous goods, operating
hours, time windows, live traffic, multiple vehicles, driver schedules, legal restrictions
beyond the supplied fields, or map freshness. Declared source metadata is not independently
verified. Test fixtures are synthetic and prove software behavior only. This is currently
available as a standalone command and the `Supplied road route` dashboard workspace. No solver API endpoint is added.


## Dashboard input

`Supplied road route` accepts a selected JSON file (up to 8 MiB) or pasted JSON (up to
256 KiB). The file takes precedence. Only the explicit calculation button invokes routing.
Results stay in session memory with source, vehicle, ordered nodes/edges, cost, distance
and excluded edges. Download the JSON result with its input hash. Failed submissions clear
the previous route. No real road network is bundled or assumed, and no server-side file
is written. All the routing limitations above remain visible with the result.

## Per-link explanation

The result JSON also includes ordered `legs` with sequence, endpoints, distance, distance
cost, toll and total link cost. Their distance and cost sums reconcile with route totals.
`excluded_edge_reasons` lists all applicable declared restrictions for each excluded link:
`closed`, `gross_weight_limit`, `height_limit`. A link can have more than one reason.
These are explanations of supplied values, not independently verified road restrictions.
The dashboard displays the per-link table and reasons in its traceability expander.
