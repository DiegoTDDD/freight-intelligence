"""Continuous minimum-cost freight flow for explicitly supplied scenarios."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import polars as pl
import scipy
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INTERPRETATION = (
    "Scenario allocation using supplied costs, capacities and node balances. "
    "Not a road itinerary or a claim of savings against an observed operation."
)


class ScenarioError(ValueError):
    """An invalid scenario or an allocation that cannot be certified."""


def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScenarioError(f"{label} must be numeric")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{label} must be finite") from error
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def identifier(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def solve_transport(scenario: dict):
    """Minimize sum(unit_cost * flow), with outgoing - incoming = balance.

    Positive balances supply freight, negative balances demand freight and zero
    balances permit transshipment. Flows are divisible and no demand is dropped.
    """
    if not isinstance(scenario, dict):
        raise ScenarioError("Scenario must be a JSON object")
    for key in ("name", "flow_unit", "cost_unit"):
        identifier(scenario.get(key), key)
    nodes, arcs = scenario.get("nodes"), scenario.get("arcs")
    if not isinstance(nodes, list) or not nodes or not isinstance(arcs, list) or not arcs:
        raise ValueError("Scenario requires nonempty nodes and arcs lists")
    node_index, balances = {}, []
    for node in nodes:
        if not isinstance(node, dict):
            raise ScenarioError("Each node must be an object")
        key = identifier(node.get("id"), "node id")
        if key in node_index:
            raise ValueError(f"Duplicate node id: {key}")
        node_index[key] = len(balances)
        balances.append(number(node.get("balance"), f"{key} balance"))
    if not math.isclose(math.fsum(balances), 0.0, abs_tol=1e-8):
        raise ValueError("Total supply must equal total demand")
    ids, costs, capacities, rows, cols, coefficients = [], [], [], [], [], []
    for i, arc in enumerate(arcs):
        if not isinstance(arc, dict):
            raise ScenarioError("Each arc must be an object")
        key = identifier(arc.get("id"), "arc id")
        if key in ids:
            raise ValueError(f"Duplicate arc id: {key}")
        origin = identifier(arc.get("origin"), f"{key} origin")
        destination = identifier(arc.get("destination"), f"{key} destination")
        if origin not in node_index or destination not in node_index or origin == destination:
            raise ValueError(f"{key}: endpoints must be distinct declared nodes")
        capacity = number(arc.get("capacity"), f"{key} capacity")
        cost = number(arc.get("unit_cost"), f"{key} unit_cost")
        if capacity < 0 or cost < 0:
            raise ValueError(f"{key}: capacity and unit_cost must be nonnegative")
        ids.append(key)
        costs.append(cost)
        capacities.append(capacity)
        rows.extend([node_index[origin], node_index[destination]])
        cols.extend([i, i])
        coefficients.extend([1.0, -1.0])
    matrix = coo_matrix((coefficients, (rows, cols)), shape=(len(nodes), len(arcs))).tocsc()
    # Necessary feasibility checks explain common input problems before invoking HiGHS.
    outgoing = {key: [] for key in node_index}
    incoming_capacity = dict.fromkeys(node_index, 0.0)
    outgoing_capacity = dict.fromkeys(node_index, 0.0)
    for arc, capacity in zip(arcs, capacities, strict=True):
        outgoing_capacity[arc["origin"]] += capacity
        incoming_capacity[arc["destination"]] += capacity
        if capacity > 0:
            outgoing[arc["origin"]].append(arc["destination"])
    for key, index in node_index.items():
        balance = balances[index]
        available = outgoing_capacity[key] if balance > 0 else incoming_capacity[key]
        if available + 1e-8 < abs(balance):
            direction = "outgoing" if balance > 0 else "incoming"
            raise ScenarioError(
                f"Scenario is infeasible: node {key!r} requires {abs(balance):.6g} "
                f"{scenario['flow_unit']} but {direction} link capacity totals only "
                f"{available:.6g}. This local capacity check does not certify other bottlenecks."
            )
    reached = {key for key, index in node_index.items() if balances[index] > 0}
    pending = list(reached)
    while pending:
        for destination in outgoing[pending.pop()]:
            if destination not in reached:
                reached.add(destination)
                pending.append(destination)
    unreachable = [
        key for key, index in node_index.items() if balances[index] < 0 and key not in reached
    ]
    if unreachable:
        raise ScenarioError(
            "Scenario is infeasible: demand nodes have no positive-capacity path from any "
            f"supply node: {', '.join(repr(key) for key in unreachable)}"
        )
    result = linprog(
        costs,
        A_eq=matrix,
        b_eq=balances,
        bounds=list(zip(np.zeros(len(arcs)), capacities, strict=True)),
        method="highs",
        options={"time_limit": 30.0},
    )
    if result.status == 2:
        raise ValueError(
            "Scenario is infeasible: connectivity or capacity cannot satisfy all balances"
        )
    if not result.success:
        raise ValueError(f"No optimal solution certified: {result.message}")
    flows = result.x
    residuals = matrix @ flows - np.asarray(balances)
    if (
        not np.isfinite(flows).all()
        or not math.isfinite(result.fun)
        or not np.allclose(residuals, 0.0, atol=1e-7, rtol=0.0)
        or (flows < -1e-7).any()
        or (flows - capacities > 1e-7).any()
    ):
        raise ValueError("Solver result failed balance/capacity verification")
    allocation = pl.DataFrame(
        [
            {
                "arc_id": arc["id"],
                "origin": arc["origin"],
                "destination": arc["destination"],
                "flow": float(flow),
                "capacity": capacity,
                "unit_cost": cost,
                "total_cost": float(flow * cost),
                "utilization": float(flow / capacity) if capacity else None,
            }
            for arc, flow, capacity, cost in zip(arcs, flows, capacities, costs, strict=True)
        ]
    )
    checks = pl.DataFrame(
        [
            {
                "node_id": key,
                "balance": balances[i],
                "net_outflow": float(balances[i] + residuals[i]),
                "residual": float(residuals[i]),
            }
            for key, i in node_index.items()
        ]
    )
    summary = {
        "scenario": scenario["name"],
        "status": "optimal",
        "solver": "scipy-highs",
        "total_cost": float(result.fun),
        "flow_unit": scenario["flow_unit"],
        "cost_unit": scenario["cost_unit"],
        "total_supply": float(sum(value for value in balances if value > 0)),
        "max_balance_residual": float(np.max(np.abs(residuals))),
        "interpretation": INTERPRETATION,
    }
    return allocation, checks, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "artifacts/optimization/transport"
    )
    args = parser.parse_args(argv)
    try:
        source = args.scenario.read_bytes()
        allocation, checks, summary = solve_transport(json.loads(source))
    except (OSError, ValueError) as error:
        parser.exit(2, f"Transport optimization failed: {error}\n")
    summary.update(
        {
            "input": str(args.scenario.resolve()),
            "input_sha256": hashlib.sha256(source).hexdigest(),
            "scipy_version": scipy.__version__,
            "polars_version": pl.__version__,
        }
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    allocation.write_parquet(args.output_dir / "allocation.parquet")
    checks.write_parquet(args.output_dir / "node_balances.parquet")
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(INTERPRETATION)
    print(f"Optimal scenario cost: {summary['total_cost']:.6g}")


if __name__ == "__main__":
    main()
