"""Compare a declared observed allocation with the same-network optimum locally."""

import argparse
import hashlib
import json
import math
from datetime import date
from pathlib import Path

from freight_intelligence.optimization.transport import (
    ScenarioError,
    identifier,
    number,
    solve_transport,
)


def compare_operation(case):
    """Validate observed flows; never certify source authenticity or realized savings."""
    if not isinstance(case, dict):
        raise ScenarioError("Case must be an object")
    provenance = case.get("provenance")
    if not isinstance(provenance, dict):
        raise ScenarioError("provenance must be an object")
    kind = provenance.get("kind")
    if kind not in ("synthetic", "declared_operating_records"):
        raise ScenarioError("kind must be synthetic or declared_operating_records")
    identifier(provenance.get("reference"), "provenance reference")
    start = date.fromisoformat(identifier(case.get("period_start"), "period_start"))
    end = date.fromisoformat(identifier(case.get("period_end"), "period_end"))
    if start > end:
        raise ScenarioError("period_start must not follow period_end")
    scenario = case.get("scenario")
    allocation, _, optimum = solve_transport(scenario)
    observed = case.get("observed_flows")
    if not isinstance(observed, list):
        raise ScenarioError("observed_flows must list every arc, including zero flows")
    flows = {}
    for row in observed:
        if not isinstance(row, dict):
            raise ScenarioError("Each observed flow must be an object")
        key = identifier(row.get("arc_id"), "arc_id")
        if key in flows:
            raise ScenarioError(f"Duplicate observed arc: {key}")
        flows[key] = number(row.get("flow"), f"{key} observed flow")
    if set(flows) != {arc["id"] for arc in scenario["arcs"]}:
        raise ScenarioError("Observed arc IDs must exactly match the scenario")
    net = {node["id"]: [] for node in scenario["nodes"]}
    costs, details = [], []
    optimized = dict(zip(allocation["arc_id"], allocation["flow"], strict=True))
    for arc in scenario["arcs"]:
        flow = flows[arc["id"]]
        if flow < 0 or flow > arc["capacity"]:
            raise ScenarioError(f"{arc['id']}: observed flow violates capacity")
        net[arc["origin"]].append(flow)
        net[arc["destination"]].append(-flow)
        cost = flow * arc["unit_cost"]
        if not math.isfinite(cost):
            raise ScenarioError("Observed cost must be finite")
        costs.append(cost)
        details.append({"arc_id": arc["id"], "observed_flow": flow,
                        "optimized_flow": optimized[arc["id"]], "observed_model_cost": cost})
    for node in scenario["nodes"]:
        if not math.isclose(math.fsum(net[node["id"]]), node["balance"], abs_tol=1e-7,
                            rel_tol=0):
            raise ScenarioError(f"{node['id']}: observed flows violate node balance")
    baseline = math.fsum(costs)
    if not math.isfinite(baseline):
        raise ScenarioError("Observed total cost must be finite")
    gap = baseline - optimum["total_cost"]
    if gap < -1e-7:
        raise ScenarioError("Observed feasible cost is below the certified optimum")
    gap = max(0.0, gap)
    return {
        "status": "comparison_complete",
        "provenance": {"kind": kind, "reference": provenance["reference"]},
        "source_authenticity": "not_independently_verified",
        "period_start": start.isoformat(), "period_end": end.isoformat(),
        "flow_unit": scenario["flow_unit"], "cost_unit": scenario["cost_unit"],
        "observed_allocation_model_cost": baseline,
        "optimized_model_cost": optimum["total_cost"],
        "modeled_opportunity": gap,
        "modeled_opportunity_percent": 100 * (gap / baseline) if baseline else None,
        "realized_savings": None,
        "x04_acceptance": "unmet: authenticated operating inputs and realized outcomes required",
        "interpretation": "Both allocations use the same supplied unit costs and constraints. "
                          "The difference is a modeled opportunity, not realized invoice savings. "
                          "Flows are divisible; vehicle schedules and omitted constraints are excluded.",
        "arcs": details,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.case.resolve() == args.output.resolve():
            raise ScenarioError("Output must differ from input")
        raw = args.case.read_bytes()
        report = compare_operation(json.loads(raw))
        report["input_sha256"] = hashlib.sha256(raw).hexdigest()
        serialized = json.dumps(report, indent=2, allow_nan=False) + "\n"
        # Exclusive creation preserves both previous reports and source records.
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
    except (OSError, ValueError, OverflowError) as error:
        parser.exit(2, f"Operating comparison failed: {error}\n")
    print("Comparison written. Modeled opportunity is not realized savings.")


if __name__ == "__main__":
    main()
