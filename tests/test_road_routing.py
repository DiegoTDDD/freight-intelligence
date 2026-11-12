import copy

import pytest

from freight_intelligence.optimization.road_routing import route_vehicle


@pytest.fixture
def routing_request():
    return {
        "network": {"source": "synthetic test graph", "cost_unit": "test currency", "nodes": ["a", "h", "b"],
                    "edges": [
                        {"id": key, "origin": start, "destination": end, "distance_km": distance,
                         "toll": toll, "max_gross_weight_t": weight, "max_height_m": 5.0, "closed": False}
                        for key, start, end, distance, toll, weight in (
                            ("direct", "a", "b", 2.0, 0.0, 10.0),
                            ("a-h", "a", "h", 2.0, 1.0, 40.0),
                            ("h-b", "h", "b", 2.0, 0.0, 40.0),
                        )]},
        "vehicle": {"id": "truck", "gross_weight_t": 20.0, "height_m": 4.0, "cost_per_km": 2.0},
    }


def solve(routing_request, start="a", end="b"):
    return route_vehicle(routing_request["network"], routing_request["vehicle"], start, end)


def test_weight_limit_forces_supported_detour_and_does_not_mutate_input(routing_request):
    original = copy.deepcopy(routing_request)
    result = solve(routing_request)
    assert result["edges"] == ["a-h", "h-b"]
    assert result["nodes"] == ["a", "h", "b"]
    assert result["total_cost"] == 9.0
    assert result["distance_km"] == 4.0
    assert result["excluded_edges"] == ["direct"]
    assert routing_request == original


def test_light_vehicle_can_take_direct_link(routing_request):
    routing_request["vehicle"]["gross_weight_t"] = 10.0
    assert solve(routing_request)["edges"] == ["direct"]


def test_direction_is_respected(routing_request):
    with pytest.raises(ValueError, match="No route"):
        solve(routing_request, "b", "a")


@pytest.mark.parametrize("restriction,value", [("closed", True), ("max_height_m", 3.0)])
def test_closure_and_height_restrictions_block_detour(routing_request, restriction, value):
    routing_request["network"]["edges"][1][restriction] = value
    with pytest.raises(ValueError, match="No route"):
        solve(routing_request)


def test_origin_equals_destination_has_zero_route(routing_request):
    result = solve(routing_request, "a", "a")
    assert result["edges"] == []
    assert result["total_cost"] == 0.0


def test_unknown_road_restrictions_are_not_assumed_open(routing_request):
    del routing_request["network"]["edges"][0]["closed"]
    with pytest.raises(ValueError, match="closed"):
        solve(routing_request)



def test_cli_preserves_existing_route_output(routing_request, tmp_path):
    import json

    from freight_intelligence.optimization.road_routing import main

    source = tmp_path / "request.json"
    output = tmp_path / "route.json"
    source.write_text(json.dumps({**routing_request, "origin": "a", "destination": "b"}))
    args = ["--input", str(source), "--output", str(output)]
    main(args)
    original = output.read_bytes()
    report = json.loads(original)
    assert report["total_cost"] == 9.0
    assert len(report["input_sha256"]) == 64
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    assert output.read_bytes() == original


def test_leg_costs_reconcile_with_route_and_exclusions_explain_limits(routing_request):
    routing_request["network"]["edges"][0]["max_height_m"] = 3.0
    routing_request["network"]["edges"][0]["closed"] = True
    result = solve(routing_request)
    assert [leg["edge_id"] for leg in result["legs"]] == result["edges"]
    assert [leg["sequence"] for leg in result["legs"]] == [1, 2]
    assert sum(leg["total_cost"] for leg in result["legs"]) == result["total_cost"]
    assert sum(leg["distance_km"] for leg in result["legs"]) == result["distance_km"]
    assert result["legs"][0]["distance_cost"] == 4.0
    assert result["legs"][0]["toll"] == 1.0
    assert result["excluded_edge_reasons"]["direct"] == ["closed", "gross_weight_limit", "height_limit"]


def test_empty_route_has_no_charged_legs(routing_request):
    assert solve(routing_request, "a", "a")["legs"] == []
