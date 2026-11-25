import copy
import json

import pytest

from freight_intelligence.optimization.operating_comparison import compare_operation, main
from freight_intelligence.optimization.transport import PROJECT_ROOT


@pytest.fixture
def case():
    return {
        "provenance": {"kind": "synthetic", "reference": "Teaching fixture only"},
        "period_start": "2026-01-01", "period_end": "2026-01-31",
        "scenario": json.loads((PROJECT_ROOT / "docs/examples/transport_scenario.json").read_text()),
        "observed_flows": [{"arc_id": key, "flow": value} for key, value in
                           [("a-x", 30), ("a-y", 50), ("b-x", 20), ("b-y", 0)]],
    }


def test_known_comparison_keeps_inputs_and_does_not_claim_savings(case):
    before = copy.deepcopy(case)
    report = compare_operation(case)
    assert report["observed_allocation_model_cost"] == 290
    assert report["optimized_model_cost"] == 190
    assert report["modeled_opportunity"] == 100
    assert report["modeled_opportunity_percent"] == pytest.approx(10000 / 290)
    assert report["realized_savings"] is None
    assert report["source_authenticity"] == "not_independently_verified"
    assert case == before


@pytest.mark.parametrize("value", [-1, 51, True, "30", float("nan"), float("inf")])
def test_bad_flow_rejected(case, value):
    case["observed_flows"][0]["flow"] = value
    with pytest.raises(ValueError):
        compare_operation(case)


def test_unbalanced_observation_rejected(case):
    case["observed_flows"][0]["flow"] = 29
    with pytest.raises(ValueError, match="balance"):
        compare_operation(case)


@pytest.mark.parametrize("change", ["missing", "duplicate", "unknown"])
def test_arc_identity_must_match(case, change):
    if change == "missing":
        case["observed_flows"].pop()
    elif change == "duplicate":
        case["observed_flows"].append(case["observed_flows"][0])
    else:
        case["observed_flows"][0]["arc_id"] = "unknown"
    with pytest.raises(ValueError):
        compare_operation(case)


def test_declared_real_records_are_not_authenticated_by_a_label(case):
    case["provenance"]["kind"] = "declared_operating_records"
    report = compare_operation(case)
    assert report["realized_savings"] is None
    assert report["x04_acceptance"].startswith("unmet")


@pytest.mark.parametrize("kind", [None, [], "verified", True])
def test_unsupported_provenance_rejected(case, kind):
    case["provenance"]["kind"] = kind
    with pytest.raises(ValueError, match="kind"):
        compare_operation(case)


def test_committed_example_report_matches_case():
    import hashlib

    raw = (PROJECT_ROOT / "docs/examples/operating_comparison_case.json").read_bytes()
    expected = compare_operation(json.loads(raw))
    expected["input_sha256"] = hashlib.sha256(raw).hexdigest()
    actual = json.loads((PROJECT_ROOT / "docs/examples/operating_comparison_report.json").read_text())
    assert actual == expected


def test_zero_cost_baseline_has_no_percentage(case):
    for arc in case["scenario"]["arcs"]:
        arc["unit_cost"] = 0
    report = compare_operation(case)
    assert report["modeled_opportunity"] == 0
    assert report["modeled_opportunity_percent"] is None


@pytest.mark.parametrize("field,value", [
    ("period_start", "2026-02-01"), ("period_end", "bad-date"),
    ("provenance", None), ("observed_flows", None),
])
def test_invalid_case_metadata(case, field, value):
    case[field] = value
    with pytest.raises(ValueError):
        compare_operation(case)


def test_cli_hash_and_preserve_existing_files(case, tmp_path):
    source, output = tmp_path / "case.json", tmp_path / "report.json"
    source.write_text(json.dumps(case))
    main(["--case", str(source), "--output", str(output)])
    report = json.loads(output.read_text())
    assert len(report["input_sha256"]) == 64
    before = output.read_bytes()
    with pytest.raises(SystemExit):
        main(["--case", str(source), "--output", str(output)])
    assert output.read_bytes() == before
    with pytest.raises(SystemExit):
        main(["--case", str(source), "--output", str(source)])
    assert json.loads(source.read_text()) == case


def test_invalid_input_does_not_create_report(case, tmp_path):
    case["observed_flows"] = []
    source, output = tmp_path / "case.json", tmp_path / "report.json"
    source.write_text(json.dumps(case))
    with pytest.raises(SystemExit):
        main(["--case", str(source), "--output", str(output)])
    assert not output.exists()
