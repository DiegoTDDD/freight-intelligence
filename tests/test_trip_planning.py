import hashlib
import io
import json
import shutil

import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.optimization.trip_planning import DEFAULT_ROOT, load_rules, plan_trip
from scripts.audit_trip_tariffs import SOURCE, audit


@pytest.mark.parametrize("highway,origin,destination", [
    ("SP-330", 20, 100), ("SP-330", 100, 20), ("SP-348", 20, 100), ("SP-348", 100, 20),
])
def test_reviewed_loaded_truck_tariffs_use_integer_cents(highway, origin, destination):
    result = plan_trip(highway=highway, origin_km=origin, destination_km=destination, axles=5)
    assert result["tolls"]["total_cents"] == 14400
    assert len(result["tolls"]["crossings"]) == 2
    assert all(line["total_cents"] == 5 * line["per_axle_cents"] for line in result["tolls"]["crossings"])
    assert result["dispatch_authorized"] is False


def test_directional_chainage_empty_segment_and_unknown_date_are_distinct():
    north = plan_trip(origin_km=81.5, destination_km=90)
    south = plan_trip(origin_km=90, destination_km=81.5)
    assert north["tolls"]["total_cents"] == 2860
    assert south["tolls"]["total_cents"] == 0
    future = plan_trip(as_of="2026-11-21")
    assert future["tolls"]["total_cents"] is None
    assert future["planning_status"] == "manual_review_required"
    assert plan_trip(as_of="2026-06-30")["tolls"]["total_cents"] is None
    assert plan_trip(as_of="2026-07-01")["tolls"]["total_cents"] == 5760
    with pytest.raises(ValueError, match="ambiguous"):
        plan_trip(origin_km=26.495)


def test_waiting_counts_as_work_and_breaks_do_not():
    result = plan_trip()
    duty = result["duty"]
    assert result["tolls"]["total_cents"] == 5760
    assert duty["work_minutes"] == 240 and duty["elapsed_minutes"] == 300
    assert duty["status"] == "within_selected_planning_limits"
    assert next(row for row in duty["timeline"] if row["activity"] == "waiting")["counts_as_work"]
    assert not next(row for row in duty["timeline"] if row["activity"] == "meal_and_driving_break")["counts_as_work"]
    assert duty["dispatch_authorized"] is False and duty["unverified"]
    assert all(a["end_minute"] == b["start_minute"] for a, b in zip(duty["timeline"], duty["timeline"][1:]))


@pytest.mark.parametrize("waiting,overtime,exceeded", [(300, False, False), (301, False, True),
                                                       (420, True, False), (421, True, True)])
def test_work_limit_boundaries(waiting, overtime, exceeded):
    result = plan_trip(waiting_minutes=waiting, overtime_authorized=overtime)["duty"]
    assert ("selected_daily_work_limit_exceeded" in result["violations"]) is exceeded


def test_previous_driving_not_reset_by_waiting_and_rest_is_uninterrupted():
    result = plan_trip(prior_drive_minutes=300, driving_minutes=60, overtime_authorized=True)["duty"]
    blocks = [row["minutes"] for row in result["timeline"] if row["activity"] == "driving"]
    assert blocks == [30, 30]
    assert next(row for row in result["timeline"] if "break" in row["activity"])["minutes"] == 60
    assert "insufficient_prior_continuous_daily_rest" in plan_trip(prior_rest_minutes=659)["duty"]["violations"]
    assert "prior_continuous_driving_limit_exceeded" in plan_trip(prior_drive_minutes=331)["duty"]["violations"]
    long = plan_trip(driving_minutes=720)["duty"]
    assert max(row["minutes"] for row in long["timeline"] if row["activity"] == "driving") == 330
    assert "shift_leaves_less_than_11_hours_in_24_hour_cycle" in long["violations"]
    assert plan_trip(shift_start_minute=1300)["planning_status"] == "manual_review_required"


@pytest.mark.parametrize("inputs", [{"axles": True}, {"axles": 10}, {"origin_km": float("nan")},
                                    {"origin_km": 19}, {"highway": "BR-116"}, {"driving_minutes": True},
                                    {"postwork_minutes": 0}, {"overtime_authorized": 1}])
def test_unsupported_or_malformed_inputs_are_rejected(inputs):
    with pytest.raises(ValueError):
        plan_trip(**inputs)


def test_api_filters_missing_rules_and_permissions(monkeypatch, tmp_path):
    with TestClient(create_app()) as client:
        assert client.get("/brazil/trip-planning?axles=5").json()["tolls"]["total_cents"] == 14400
        assert client.get("/brazil/trip-planning?origin_km=26.495").status_code == 422
        assert client.get("/brazil/trip-planning?axles=1").status_code == 422
        assert client.post("/brazil/trip-planning", json={}).status_code == 405
    with TestClient(create_app(trip_rules_dir=tmp_path)) as client:
        assert client.get("/brazil/trip-planning").status_code == 503
    key = "trip-key-" + "x" * 32
    registry = tmp_path / "users.json"
    registry.write_text(json.dumps({"users": [{"id": "reader", "key_sha256": hashlib.sha256(key.encode()).hexdigest(),
                                             "enabled": True, "permissions": ["evaluation"]}]}), encoding="utf-8")
    monkeypatch.setenv("LOGINEXUS_REQUIRE_AUTH", "true")
    monkeypatch.setenv("LOGINEXUS_API_USERS_FILE", str(registry))
    monkeypatch.delenv("LOGINEXUS_API_KEY", raising=False)
    with TestClient(create_app()) as client:
        assert client.get("/brazil/trip-planning").status_code == 401
        assert client.get("/brazil/trip-planning", headers={"X-API-Key": key}).status_code == 403


def test_changed_rule_file_is_not_served(tmp_path):
    root = tmp_path / "rules"
    shutil.copytree(DEFAULT_ROOT, root)
    (root / "rules.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="integrity"):
        load_rules(root)


class Response(io.BytesIO):
    def __init__(self, raw, url=SOURCE, declared=None):
        super().__init__(raw)
        self.url = url
        self.headers = {} if declared is None else {"Content-Length": str(declared)}

    def geturl(self):
        return self.url


@pytest.mark.parametrize("defect", ["changed", "html", "redirect", "truncated", "oversized", "network"])
def test_tariff_audit_changed_and_failure_paths_keep_served_rules(tmp_path, defect):
    raw = b"%PDF-1.7\nreview candidate\n%%EOF"
    before = (DEFAULT_ROOT / "rules.json").read_bytes()
    response = Response(raw)
    if defect == "html":
        response = Response(b"<html>unavailable</html>")
    elif defect == "redirect":
        response.url = "https://example.com/other.pdf"
    elif defect == "truncated":
        response.headers["Content-Length"] = str(len(raw) + 1)
    elif defect == "oversized":
        response = Response(b"%PDF-" + b"x" * 1024**2 + b"%%EOF")

    def opener(*args, **kwargs):
        if defect == "network":
            raise TimeoutError("Test connection timeout")
        return response

    path = tmp_path / "report.json"
    if defect == "changed":
        assert audit(path, opener=opener)["status"] == "source_changed_requires_review"
    else:
        with pytest.raises((ValueError, TimeoutError)):
            audit(path, opener=opener)
        assert json.loads(path.read_bytes())["status"] == "validation_failed"
    assert before == (DEFAULT_ROOT / "rules.json").read_bytes()
    with pytest.raises(FileExistsError):
        audit(path, opener=opener)


def test_tariff_audit_unchanged_uses_full_reviewed_pdf_hash(tmp_path):
    root = tmp_path / "rules"
    shutil.copytree(DEFAULT_ROOT, root)
    raw = b"%PDF-1.7\nreviewed fixture\n%%EOF"
    rules = load_rules(root)
    next(s for s in rules["sources"] if s["id"] == "tariffs")["sha256"] = hashlib.sha256(raw).hexdigest()
    payload = (json.dumps(rules) + "\n").encode()
    (root / "rules.json").write_bytes(payload)
    manifest = json.loads((root / "manifest.json").read_bytes())
    manifest["files"][0].update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    (root / "manifest.json").write_bytes(json.dumps(manifest).encode())
    result = audit(tmp_path / "report.json", root=root, opener=lambda *a, **k: Response(raw, declared=len(raw)))
    assert result["status"] == "unchanged" and result["automatic_promotion"] is False
    assert result["bytes"] == len(raw)
