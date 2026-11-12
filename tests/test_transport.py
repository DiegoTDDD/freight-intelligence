import copy
import json

import polars as pl
import pytest

from freight_intelligence.optimization.transport import PROJECT_ROOT, main, solve_transport


@pytest.fixture
def scenario():
    return json.loads((PROJECT_ROOT / "docs/examples/transport_scenario.json").read_text())


def test_known_optimum_and_balances(scenario):
    original = copy.deepcopy(scenario)
    allocation, checks, summary = solve_transport(scenario)
    assert summary["total_cost"] == pytest.approx(190)
    assert dict(zip(allocation["arc_id"], allocation["flow"], strict=True)) == {
        "a-x": 50.0,
        "a-y": 30.0,
        "b-x": 0.0,
        "b-y": 20.0,
    }
    assert checks["residual"].abs().max() < 1e-7
    assert (allocation["flow"] <= allocation["capacity"]).all()
    assert scenario == original


def test_capacity_forces_more_expensive_route(scenario):
    scenario["arcs"][0]["capacity"] = 40
    allocation, _, summary = solve_transport(scenario)
    assert summary["total_cost"] == pytest.approx(240)
    assert allocation.filter(pl.col("arc_id") == "a-x")["flow"].item() == 40


def test_fractional_transshipment_and_zero_capacity():
    scenario = {
        "name": "fractional",
        "flow_unit": "units",
        "cost_unit": "cost",
        "nodes": [
            {"id": "a", "balance": 1.5},
            {"id": "hub", "balance": 0},
            {"id": "b", "balance": -1.5},
        ],
        "arcs": [
            {"id": "a-h", "origin": "a", "destination": "hub", "capacity": 2.0, "unit_cost": 1.0},
            {"id": "h-b", "origin": "hub", "destination": "b", "capacity": 2.0, "unit_cost": 2.0},
            {"id": "closed", "origin": "a", "destination": "b", "capacity": 0.0, "unit_cost": 0.0},
        ],
    }
    allocation, checks, summary = solve_transport(scenario)
    assert summary["total_cost"] == pytest.approx(4.5)
    assert allocation["flow"].to_list() == [1.5, 1.5, 0.0]
    assert allocation.filter(pl.col("arc_id") == "closed")["utilization"].item() is None
    assert checks.filter(pl.col("node_id") == "hub")["net_outflow"].item() == 0.0


def test_infeasible_capacity_has_no_partial_solution(scenario):
    scenario["arcs"][0]["capacity"] = 1
    scenario["arcs"][1]["capacity"] = 1
    with pytest.raises(ValueError, match="infeasible"):
        solve_transport(scenario)


def test_disconnected_balanced_network_is_infeasible(scenario):
    scenario["arcs"] = scenario["arcs"][:1]
    with pytest.raises(ValueError, match="infeasible"):
        solve_transport(scenario)


def test_unbalanced_supply_rejected(scenario):
    scenario["nodes"][0]["balance"] = 81
    with pytest.raises(ValueError, match="supply must equal"):
        solve_transport(scenario)


@pytest.mark.parametrize(
    "field,value",
    [
        ("capacity", -1),
        ("unit_cost", -1),
        ("capacity", float("nan")),
        ("unit_cost", float("inf")),
        ("capacity", True),
        ("capacity", "50"),
        ("origin", "missing"),
        ("destination", "supply-a"),
        ("id", ""),
    ],
)
def test_bad_arc_values_rejected(scenario, field, value):
    scenario["arcs"][0][field] = value
    with pytest.raises(ValueError):
        solve_transport(scenario)


@pytest.mark.parametrize("kind", ["nodes", "arcs"])
def test_duplicate_ids_rejected(scenario, kind):
    scenario[kind].append(copy.deepcopy(scenario[kind][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        solve_transport(scenario)


@pytest.mark.parametrize("scenario", [None, {}, {"name": "x"}, []])
def test_incomplete_scenario_rejected(scenario):
    with pytest.raises(ValueError):
        solve_transport(scenario)


def test_zero_balances_and_costs(scenario):
    for node in scenario["nodes"]:
        node["balance"] = 0
    for arc in scenario["arcs"]:
        arc["unit_cost"] = 0
    _, checks, summary = solve_transport(scenario)
    assert summary["total_cost"] == 0
    assert checks["residual"].abs().max() == 0


def test_cli_records_provenance_without_modifying_scenario(tmp_path, scenario):
    source = tmp_path / "scenario.json"
    source.write_text(json.dumps(scenario))
    before = source.read_bytes()
    output = tmp_path / "result"
    main(["--scenario", str(source), "--output-dir", str(output)])
    assert source.read_bytes() == before
    summary = json.loads((output / "summary.json").read_text())
    assert summary["total_cost"] == 190
    assert len(summary["input_sha256"]) == 64
    assert "Not a road itinerary" in summary["interpretation"]
    assert pl.read_parquet(output / "allocation.parquet").height == 4
    assert pl.read_parquet(output / "node_balances.parquet").height == 4


def test_cli_invalid_input_creates_no_outputs(tmp_path):
    source = tmp_path / "scenario.json"
    source.write_text('{"bad":true}')
    output = tmp_path / "result"
    with pytest.raises(SystemExit) as error:
        main(["--scenario", str(source), "--output-dir", str(output)])
    assert error.value.code == 2
    assert not output.exists()


def test_capacity_failure_identifies_node_and_required_amount(scenario):
    scenario["arcs"][0]["capacity"] = 1
    scenario["arcs"][1]["capacity"] = 1
    with pytest.raises(ValueError, match="supply-a.*80.*outgoing.*2"):
        solve_transport(scenario)


def test_disconnected_demand_cycle_is_explained():
    # Local node capacities are sufficient, but the demand component has no supply path.
    scenario = {
        "name": "separate components", "flow_unit": "units", "cost_unit": "cost",
        "nodes": [{"id": "s", "balance": 5}, {"id": "hub", "balance": 0},
                  {"id": "d", "balance": -5}, {"id": "loop", "balance": 0}],
        "arcs": [{"id": name, "origin": origin, "destination": destination,
                  "capacity": 10, "unit_cost": 1}
                 for name, origin, destination in (("s-h", "s", "hub"), ("h-s", "hub", "s"),
                                                   ("d-l", "d", "loop"), ("l-d", "loop", "d"))],
    }
    with pytest.raises(ValueError, match="no positive-capacity path.*'d'"):
        solve_transport(scenario)
