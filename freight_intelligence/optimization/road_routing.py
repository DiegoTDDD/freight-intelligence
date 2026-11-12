"""Directed routing on a supplied road graph with explicit vehicle limits and costs."""

import argparse
import hashlib
import heapq
import json
from pathlib import Path

from freight_intelligence.optimization.transport import identifier, number


def route_vehicle(network, vehicle, origin, destination):
    """Find a minimum supplied-cost path; no maps, traffic or road restrictions are inferred."""
    if not isinstance(network, dict) or not isinstance(vehicle, dict):
        raise TypeError("Network and vehicle must be objects")
    source = identifier(network.get("source"), "network source")
    currency = identifier(network.get("cost_unit"), "cost unit")
    nodes, edges = network.get("nodes"), network.get("edges")
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 10000:
        raise ValueError("Supply 1-10000 node ids")
    for node in nodes:
        identifier(node, "node id")
    if len(set(nodes)) != len(nodes):
        raise ValueError("Duplicate node ids")
    if not isinstance(edges, list) or not 1 <= len(edges) <= 50000:
        raise ValueError("Supply 1-50000 directed edges")
    if origin not in nodes or destination not in nodes:
        raise ValueError("Origin and destination must be declared nodes")
    identifier(vehicle.get("id"), "vehicle id")
    weight = number(vehicle.get("gross_weight_t"), "gross weight in metric tonnes")
    height = number(vehicle.get("height_m"), "height in metres")
    per_km = number(vehicle.get("cost_per_km"), "cost per km")
    if weight <= 0 or height <= 0 or per_km < 0:
        raise ValueError("Vehicle weight/height must be positive and cost nonnegative")
    adjacency = {node: [] for node in nodes}
    identifiers, excluded = set(), []
    edge_details, excluded_reasons = {}, {}
    for edge in edges:
        if not isinstance(edge, dict):
            raise TypeError("Each edge must be an object")
        key = identifier(edge.get("id"), "edge id")
        if key in identifiers:
            raise ValueError("Duplicate edge ids")
        identifiers.add(key)
        start, end = edge.get("origin"), edge.get("destination")
        if start not in adjacency or end not in adjacency or start == end:
            raise ValueError("Edges require distinct declared endpoints")
        distance = number(edge.get("distance_km"), "distance in km")
        toll = number(edge.get("toll"), "toll")
        max_weight = number(edge.get("max_gross_weight_t"), "maximum gross weight")
        max_height = number(edge.get("max_height_m"), "maximum height")
        if distance <= 0 or toll < 0 or max_weight <= 0 or max_height <= 0:
            raise ValueError("Distance/limits must be positive and toll nonnegative")
        closed = edge.get("closed")
        if type(closed) is not bool:
            raise ValueError("Every edge must declare a boolean closed flag")
        if closed or weight > max_weight or height > max_height:
            excluded.append(key)
            excluded_reasons[key] = [
                reason for reason, applies in (
                    ("closed", closed), ("gross_weight_limit", weight > max_weight),
                    ("height_limit", height > max_height),
                ) if applies
            ]
            continue
        cost = number(distance * per_km + toll, "computed edge cost")
        edge_details[key] = {
            "edge_id": key, "origin": start, "destination": end, "distance_km": distance,
            "distance_cost": distance * per_km, "toll": toll, "total_cost": cost,
        }
        adjacency[start].append((end, key, distance, cost))
    best = {origin: (0.0, 0.0)}
    previous = {}
    pending = [(0.0, 0.0, origin)]
    while pending:
        cost, distance, node = heapq.heappop(pending)
        if (cost, distance) != best[node]:
            continue
        if node == destination:
            break
        for target, edge_id, length, edge_cost in adjacency[node]:
            candidate = (number(cost + edge_cost, "path cost"), number(distance + length, "path distance"))
            if target not in best or candidate < best[target]:
                best[target] = candidate
                previous[target] = (node, edge_id)
                heapq.heappush(pending, (*candidate, target))
    if destination not in best:
        raise ValueError("No route satisfies the supplied directed links and vehicle restrictions")
    path_nodes, path_edges = [destination], []
    while path_nodes[-1] != origin:
        parent, edge_id = previous[path_nodes[-1]]
        path_nodes.append(parent)
        path_edges.append(edge_id)
    legs = [dict(edge_details[key], sequence=index) for index, key in enumerate(path_edges[::-1], 1)]
    return {
        "status": "optimal_supplied_graph", "source": source, "vehicle_id": vehicle["id"],
        "origin": origin, "destination": destination, "cost_unit": currency,
        "total_cost": best[destination][0], "distance_km": best[destination][1],
        "nodes": path_nodes[::-1], "edges": path_edges[::-1], "excluded_edges": sorted(excluded),
        "legs": legs, "excluded_edge_reasons": excluded_reasons,
        "interpretation": "Minimum-cost path on supplied directed links and declared vehicle "
        "restrictions only. Not a verified driving itinerary; no live traffic, turn rules, "
        "hazardous-goods rules, time windows or regulatory validation.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.input.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("Routing input exceeds 8 MiB")
        raw = args.input.read_bytes()
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise TypeError("Routing request must be an object")
        result = route_vehicle(request.get("network"), request.get("vehicle"),
                               request.get("origin"), request.get("destination"))
        result["input_sha256"] = hashlib.sha256(raw).hexdigest()
        with args.output.open("x", encoding="utf-8") as output:
            output.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"Supplied-network routing failed: {error}\n")
    print("Supplied-network route written; existing outputs preserved.")


if __name__ == "__main__":
    main()
