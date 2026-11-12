import copy
import hashlib
import io
import json
import zipfile
from pathlib import Path

import polars as pl
import pytest
from streamlit.testing.v1 import AppTest

from freight_intelligence.optimization.planner import (
    MAX_ARCS,
    MAX_IMPORT_BYTES,
    MAX_NODES,
    compare_solutions,
    parse_scenario_json,
    simulate_scenario,
    snapshot_solution,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def scenario():
    return json.loads((ROOT / "docs/examples/transport_scenario.json").read_text())


def test_simulation_returns_reproducible_input_and_solution_bundle(scenario):
    original = copy.deepcopy(scenario)
    result = simulate_scenario(scenario)
    assert scenario == original
    assert result["summary"]["total_cost"] == 190
    with zipfile.ZipFile(io.BytesIO(result["archive"])) as bundle:
        assert set(bundle.namelist()) == {
            "scenario.json",
            "summary.json",
            "allocation.parquet",
            "node_balances.parquet",
            "allocation.csv",
            "node_balances.csv",
        }
        assert json.loads(bundle.read("scenario.json")) == scenario
        summary = json.loads(bundle.read("summary.json"))
        assert summary["input_sha256"] == hashlib.sha256(bundle.read("scenario.json")).hexdigest()
        assert pl.read_parquet(bundle.read("allocation.parquet")).equals(result["allocation"])
        assert pl.read_parquet(bundle.read("node_balances.parquet")).height == 4


@pytest.mark.parametrize("key,limit", [("nodes", MAX_NODES), ("arcs", MAX_ARCS)])
def test_interactive_size_limits_reject_before_solver(scenario, monkeypatch, key, limit):
    from freight_intelligence.optimization import planner

    scenario[key] = [scenario[key][0]] * (limit + 1)

    def fail(*args, **kwargs):
        raise AssertionError("Oversized scenario reached solver")

    monkeypatch.setattr(planner, "solve_transport", fail)
    with pytest.raises(ValueError, match="Interactive scenarios"):
        simulate_scenario(scenario)


def test_invalid_or_infeasible_scenario_has_no_result(scenario):
    scenario["nodes"][0]["balance"] = 999
    with pytest.raises(ValueError, match="supply must equal"):
        simulate_scenario(scenario)
    with pytest.raises(TypeError):
        simulate_scenario(None)


def open_planner(monkeypatch, tmp_path):
    monkeypatch.setenv("LOGINEXUS_DASHBOARD_DATA_ROOT", str(tmp_path))
    app = AppTest.from_file(str(ROOT / "dashboards/app.py"), default_timeout=20).run()
    app.selectbox(key="workspace").select("Scenario planner").run()
    assert not app.exception
    return app


def test_opening_planner_does_not_run_solver(tmp_path, monkeypatch):
    from freight_intelligence.optimization import planner

    def fail(*args, **kwargs):
        raise AssertionError("Opening planner ran solver")

    monkeypatch.setattr(planner, "solve_transport", fail)
    app = open_planner(monkeypatch, tmp_path)
    assert not app.metric
    assert not list(tmp_path.iterdir())


def test_form_submission_solves_and_does_not_write_files(tmp_path, monkeypatch):
    app = open_planner(monkeypatch, tmp_path)
    app.button(key="planner_submit").click().run()
    assert not app.exception
    assert any(
        item.label == "Simulated total cost" and item.value == "190.00" for item in app.metric
    )
    assert app.session_state["planner_solution"]["archive"]
    assert not list(tmp_path.iterdir())


def test_invalid_resubmission_clears_previous_solution(tmp_path, monkeypatch):
    app = open_planner(monkeypatch, tmp_path)
    app.button(key="planner_submit").click().run()
    app.text_input(key="planner_name").set_value("")
    app.button(key="planner_submit").click().run()
    assert not app.exception and app.error
    assert not app.metric
    assert "planner_solution" not in app.session_state


def test_editing_link_capacity_changes_submitted_solution(tmp_path, monkeypatch):
    app = open_planner(monkeypatch, tmp_path)
    app.session_state["planner_arcs"] = {
        "edited_rows": {0: {"capacity": 40.0}},
        "added_rows": [],
        "deleted_rows": [],
    }
    app.button(key="planner_submit").click().run()
    assert not app.exception
    assert any(
        item.label == "Simulated total cost" and item.value == "240.00" for item in app.metric
    )


def test_json_import_supports_utf8_bom_and_does_not_run_solver(scenario, monkeypatch):
    from freight_intelligence.optimization import planner

    def fail(*args, **kwargs):
        raise AssertionError("Import invoked solver")

    monkeypatch.setattr(planner, "solve_transport", fail)
    scenario["name"] = "Cenário próprio"
    assert (
        parse_scenario_json(b"\xef\xbb\xbf" + json.dumps(scenario, ensure_ascii=False).encode())
        == scenario
    )


def test_exported_scenario_can_be_reimported(scenario):
    result = simulate_scenario(scenario)
    with zipfile.ZipFile(io.BytesIO(result["archive"])) as bundle:
        restored = parse_scenario_json(bundle.read("scenario.json"))
    assert simulate_scenario(restored)["summary"]["total_cost"] == 190


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"invalid",
        b"null",
        b"\xff",
        b'{"name":"one","name":"two"}',
        b" " * (MAX_IMPORT_BYTES + 1),
    ],
    ids=["empty", "invalid-json", "non-object", "invalid-utf8", "duplicate-fields", "oversized"],
)
def test_invalid_json_import_rejected(payload):
    with pytest.raises(ValueError):
        parse_scenario_json(payload)


@pytest.mark.parametrize(
    "case",
    [
        "extra",
        "missing",
        "duplicate_node",
        "duplicate_arc",
        "nonfinite",
        "negative_cost",
        "unbalanced",
        "too_many",
        "unknown_endpoint",
    ],
)
def test_import_contract_rejects_bad_scenarios(scenario, case):
    if case == "extra":
        scenario["notes"] = "unknown field"
    elif case == "missing":
        del scenario["flow_unit"]
    elif case == "duplicate_node":
        scenario["nodes"].append(scenario["nodes"][0])
    elif case == "duplicate_arc":
        scenario["arcs"].append(scenario["arcs"][0])
    elif case == "nonfinite":
        scenario["nodes"][0]["balance"] = float("nan")
    elif case == "negative_cost":
        scenario["arcs"][0]["unit_cost"] = -1
    elif case == "unbalanced":
        scenario["nodes"][0]["balance"] = 99
    elif case == "too_many":
        scenario["nodes"] *= MAX_NODES
    else:
        scenario["arcs"][0]["destination"] = "missing"
    with pytest.raises(ValueError):
        parse_scenario_json(json.dumps(scenario).encode())


def test_ui_import_replaces_edits_and_requires_explicit_simulation(tmp_path, monkeypatch, scenario):
    app = open_planner(monkeypatch, tmp_path)
    app.button(key="planner_submit").click().run()
    assert app.metric
    scenario["name"] = "Imported capacity scenario"
    scenario["arcs"][0]["capacity"] = 40
    app.text_area(key="planner_import_json").set_value(json.dumps(scenario))
    app.button(key="planner_import").click().run()
    assert not app.exception
    assert not app.metric
    assert app.text_input(key="planner_name").value == scenario["name"]
    assert app.dataframe[1].value["capacity"].iloc[0] == 40
    assert app.session_state["planner_revision"] == 1
    app.button(key="planner_submit").click().run()
    assert not app.exception
    assert any(
        item.label == "Simulated total cost" and item.value == "240.00" for item in app.metric
    )
    assert not list(tmp_path.iterdir())


def test_failed_import_preserves_work_and_reset_restores_example(tmp_path, monkeypatch, scenario):
    app = open_planner(monkeypatch, tmp_path)
    app.text_input(key="planner_name").set_value("My current work")
    app.button(key="planner_submit").click().run()
    app.text_area(key="planner_import_json").set_value("not json")
    app.button(key="planner_import").click().run()
    assert not app.exception and app.error
    assert app.text_input(key="planner_name").value == "My current work"
    assert app.metric
    app.button(key="planner_reset").click().run()
    assert not app.exception and not app.metric
    assert app.text_input(key="planner_name").value == scenario["name"]


def test_reference_comparison_cost_flow_and_archive(scenario, monkeypatch):
    from freight_intelligence.optimization import planner

    reference = simulate_scenario(scenario)
    scenario["arcs"][0]["capacity"] = 40
    candidate = simulate_scenario(scenario)

    def fail(*args, **kwargs):
        raise AssertionError("Comparison reran the solver")

    monkeypatch.setattr(planner, "solve_transport", fail)
    report = compare_solutions(reference, candidate)
    assert report["summary"]["cost_change"] == 50
    assert report["summary"]["relative_cost_change"] == pytest.approx(50 / 190)
    assert report["flow_changes"].filter(pl.col("arc_id") == "a-x")["flow_change"].item() == -10
    with zipfile.ZipFile(io.BytesIO(report["archive"])) as bundle:
        assert len(bundle.namelist()) == 14
        assert json.loads(bundle.read("reference/summary.json"))["total_cost"] == 190
        assert json.loads(bundle.read("candidate/summary.json"))["total_cost"] == 240
        for prefix in ("reference", "candidate"):
            summary = json.loads(bundle.read(f"{prefix}/summary.json"))
            assert (
                summary["input_sha256"]
                == hashlib.sha256(bundle.read(f"{prefix}/scenario.json")).hexdigest()
            )


def test_reference_snapshot_is_independent(scenario):
    current = simulate_scenario(scenario)
    reference = snapshot_solution(current)
    current["summary"]["total_cost"] = 999
    assert reference["summary"]["total_cost"] == 190


@pytest.mark.parametrize("change", ["flow_unit", "cost_unit", "balances"])
def test_comparison_rejects_incompatible_demands_and_units(scenario, change):
    reference = simulate_scenario(scenario)
    if change == "balances":
        scenario["nodes"][0]["balance"] += 1
        scenario["nodes"][2]["balance"] -= 1
    else:
        scenario[change] = "different unit"
    candidate = simulate_scenario(scenario)
    with pytest.raises(ValueError, match="Comparison requires"):
        compare_solutions(reference, candidate)


def test_zero_reference_cost_has_no_relative_percentage(scenario):
    candidate = simulate_scenario(scenario)
    for arc in scenario["arcs"]:
        arc["unit_cost"] = 0
    reference = simulate_scenario(scenario)
    summary = compare_solutions(reference, candidate)["summary"]
    assert summary["cost_change"] == 190
    assert summary["relative_cost_change"] is None


def test_comparison_represents_added_and_removed_links(scenario):
    reference = simulate_scenario(scenario)
    scenario["arcs"][0]["id"] = "replacement"
    report = compare_solutions(reference, simulate_scenario(scenario))
    rows = report["flow_changes"]
    assert rows.filter(pl.col("arc_id") == "a-x")["candidate_flow"].item() == 0
    assert rows.filter(pl.col("arc_id") == "replacement")["reference_flow"].item() == 0
    assert report["summary"]["cost_change"] == 0


def test_ui_reference_survives_import_and_can_be_cleared(tmp_path, monkeypatch, scenario):
    app = open_planner(monkeypatch, tmp_path)
    app.button(key="planner_submit").click().run()
    app.button(key="planner_use_reference").click().run()
    scenario["name"] = "Tighter capacity candidate"
    scenario["arcs"][0]["capacity"] = 40
    app.text_area(key="planner_import_json").set_value(json.dumps(scenario))
    app.button(key="planner_import").click().run()
    app.button(key="planner_submit").click().run()
    assert not app.exception
    assert app.session_state["planner_reference"]["summary"]["total_cost"] == 190
    assert any(
        item.label == "Cost change vs reference" and item.value == "+50.00" for item in app.metric
    )
    app.button(key="planner_clear_reference").click().run()
    assert not app.exception
    assert not any(item.label == "Cost change vs reference" for item in app.metric)
    assert any(
        item.label == "Simulated total cost" and item.value == "240.00" for item in app.metric
    )
    assert not list(tmp_path.iterdir())
