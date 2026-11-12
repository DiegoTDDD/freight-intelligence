"""Bounded in-memory transport simulations and downloadable result bundles."""

import copy
import hashlib
import io
import json
import math
import zipfile

import scipy

from freight_intelligence.optimization.transport import identifier, number, solve_transport

MAX_NODES = 100
MAX_ARCS = 500
MAX_IMPORT_BYTES = 256 * 1024


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Scenario JSON contains duplicate field names")
        result[key] = value
    return result


def parse_scenario_json(payload: bytes):
    if not isinstance(payload, bytes):
        raise TypeError("Scenario import requires UTF-8 JSON bytes")
    if not payload or len(payload) > MAX_IMPORT_BYTES:
        raise ValueError("Scenario JSON must be nonempty and at most 256 KiB")
    scenario = json.loads(payload.decode("utf-8-sig"), object_pairs_hook=unique_fields)
    fields = {"name", "flow_unit", "cost_unit", "nodes", "arcs"}
    if not isinstance(scenario, dict) or set(scenario) != fields:
        raise ValueError("Provide exactly name, flow_unit, cost_unit, nodes and arcs")
    for key, limit in [("name", 140), ("flow_unit", 100), ("cost_unit", 100)]:
        if len(identifier(scenario[key], key)) > limit:
            raise ValueError(f"{key} exceeds {limit} characters")
    nodes, arcs = scenario["nodes"], scenario["arcs"]
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= MAX_NODES:
        raise ValueError("Import requires 1 to 100 nodes")
    if not isinstance(arcs, list) or not 1 <= len(arcs) <= MAX_ARCS:
        raise ValueError("Import requires 1 to 500 links")
    node_ids, arc_ids, balances = set(), set(), []
    for node in nodes:
        if not isinstance(node, dict) or set(node) != {"id", "balance"}:
            raise ValueError("Each node requires exactly id and balance")
        key = identifier(node["id"], "node id")
        if key in node_ids:
            raise ValueError("Duplicate node identifiers")
        node_ids.add(key)
        balances.append(number(node["balance"], "node balance"))
    for arc in arcs:
        if not isinstance(arc, dict) or set(arc) != {
            "id",
            "origin",
            "destination",
            "capacity",
            "unit_cost",
        }:
            raise ValueError(
                "Each link requires exactly id, origin, destination, capacity and unit_cost"
            )
        key = identifier(arc["id"], "link id")
        if key in arc_ids:
            raise ValueError("Duplicate link identifiers")
        arc_ids.add(key)
        if (
            arc["origin"] not in node_ids
            or arc["destination"] not in node_ids
            or arc["origin"] == arc["destination"]
        ):
            raise ValueError("Links must join distinct declared nodes")
        if number(arc["capacity"], "capacity") < 0 or number(arc["unit_cost"], "unit_cost") < 0:
            raise ValueError("Capacities and costs must be nonnegative")
    if not math.isclose(math.fsum(balances), 0.0, abs_tol=1e-8):
        raise ValueError("Total supply must equal total demand")
    return scenario


def replace_planner_inputs(state, scenario):
    """Apply a new seed before form widgets are rendered; clear stale edits/results."""
    for key in (
        "planner_name",
        "planner_flow_unit",
        "planner_cost_unit",
        "planner_nodes",
        "planner_arcs",
        "planner_solution",
    ):
        state.pop(key, None)
    state["planner_seed"] = scenario
    state["planner_name"] = scenario["name"]
    state["planner_flow_unit"] = scenario["flow_unit"]
    state["planner_cost_unit"] = scenario["cost_unit"]
    state["planner_revision"] = state.get("planner_revision", 0) + 1


def simulate_scenario(scenario):
    if not isinstance(scenario, dict):
        raise TypeError("Scenario must be an object")
    nodes, arcs = scenario.get("nodes"), scenario.get("arcs")
    if not isinstance(nodes, list) or not isinstance(arcs, list):
        raise TypeError("Provide node and link tables")
    if len(nodes) > MAX_NODES or len(arcs) > MAX_ARCS:
        raise ValueError(
            f"Interactive scenarios support at most {MAX_NODES} nodes and {MAX_ARCS} links"
        )
    allocation, checks, summary = solve_transport(scenario)
    source = (json.dumps(scenario, sort_keys=True, indent=2, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    summary.update(
        {
            "input_sha256": hashlib.sha256(source).hexdigest(),
            "input": "scenario.json",
            "execution": "interactive_session",
            "scipy_version": scipy.__version__,
        }
    )
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("scenario.json", source)
        bundle.writestr("summary.json", json.dumps(summary, indent=2, allow_nan=False) + "\n")
        for name, frame in [("allocation", allocation), ("node_balances", checks)]:
            parquet = io.BytesIO()
            frame.write_parquet(parquet)
            bundle.writestr(f"{name}.parquet", parquet.getvalue())
            bundle.writestr(f"{name}.csv", frame.write_csv())
    return {
        "summary": summary,
        "allocation": allocation,
        "node_balances": checks,
        "archive": archive.getvalue(),
    }


def snapshot_solution(solution):
    """Keep a session-local reference independent of later edits or simulations."""
    return copy.deepcopy(solution)


def compare_solutions(reference, candidate):
    before, after = reference["summary"], candidate["summary"]
    if before["status"] != "optimal" or after["status"] != "optimal":
        raise ValueError("Compare only successfully solved scenarios")
    for unit in ("flow_unit", "cost_unit"):
        if before[unit] != after[unit]:
            raise ValueError("Comparison requires matching flow and cost units")
    before_nodes = {row["node_id"]: row["balance"] for row in reference["node_balances"].to_dicts()}
    after_nodes = {row["node_id"]: row["balance"] for row in candidate["node_balances"].to_dicts()}
    if before_nodes.keys() != after_nodes.keys() or any(
        not math.isclose(value, after_nodes[key], rel_tol=0.0, abs_tol=1e-8)
        for key, value in before_nodes.items()
    ):
        raise ValueError("Comparison requires the same nodes and supply/demand balances")

    def flows(solution):
        return {
            (row["arc_id"], row["origin"], row["destination"]): row["flow"]
            for row in solution["allocation"].to_dicts()
        }

    before_flows, after_flows = flows(reference), flows(candidate)
    changes = []
    for key in sorted(before_flows.keys() | after_flows.keys()):
        old, new = before_flows.get(key, 0.0), after_flows.get(key, 0.0)
        changes.append(
            {
                "arc_id": key[0],
                "origin": key[1],
                "destination": key[2],
                "reference_flow": old,
                "candidate_flow": new,
                "flow_change": new - old,
            }
        )
    delta = after["total_cost"] - before["total_cost"]
    relative = delta / before["total_cost"] if before["total_cost"] else None
    if relative is not None and not math.isfinite(relative):
        relative = None
    summary = {
        "reference_name": before["scenario"],
        "candidate_name": after["scenario"],
        "reference_input_sha256": before["input_sha256"],
        "candidate_input_sha256": after["input_sha256"],
        "flow_unit": before["flow_unit"],
        "cost_unit": before["cost_unit"],
        "reference_cost": before["total_cost"],
        "candidate_cost": after["total_cost"],
        "cost_change": delta,
        "relative_cost_change": relative,
        "interpretation": "Difference between two supplied scenarios with matching demand and units; not measured operational savings.",
    }
    import polars as pl

    frame = pl.DataFrame(changes)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("comparison.json", json.dumps(summary, indent=2, allow_nan=False) + "\n")
        bundle.writestr("flow_changes.csv", frame.write_csv())
        for prefix, solution in [("reference", reference), ("candidate", candidate)]:
            with zipfile.ZipFile(io.BytesIO(solution["archive"])) as original:
                for name in (
                    "scenario.json",
                    "summary.json",
                    "allocation.parquet",
                    "allocation.csv",
                    "node_balances.parquet",
                    "node_balances.csv",
                ):
                    bundle.writestr(f"{prefix}/{name}", original.read(name))
    return {"summary": summary, "flow_changes": frame, "archive": archive.getvalue()}
