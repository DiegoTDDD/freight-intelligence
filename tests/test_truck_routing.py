import json

import pytest

from freight_intelligence.optimization import truck_routing as routing

VEHICLE = routing.PROFILES["Urban rigid truck (example)"]
ORIGIN, DESTINATION = [-46.6333, -23.5505], [-47.0608, -22.9056]


def encoded(points):
    previous = [0, 0]
    output = ""
    for point in points:
        for index, value in enumerate(reversed(point)):
            current = round(value * 1e6)
            delta = current - previous[index]
            previous[index] = current
            number = ~(delta << 1) if delta < 0 else delta << 1
            while number >= 32:
                output += chr((32 | (number & 31)) + 63)
                number >>= 5
            output += chr(number + 63)
    return output


def response():
    summary = {"length": 100.0, "time": 6000.0}
    return {"trip": {"status": 0, "units": "kilometers", "summary": summary,
                     "legs": [{"summary": dict(summary),
                               "shape": encoded([ORIGIN, DESTINATION]),
                               "maneuvers": [{"instruction": "Arrive at destination"}]}]}}


def test_profile_sent_as_truck_without_relaxed_access():
    payload = routing.route_payload(ORIGIN, DESTINATION, VEHICLE)
    assert payload["costing"] == "truck"
    options = payload["costing_options"]["truck"]
    assert all(options[key] == value for key, value in VEHICLE.items())
    assert options["hgv_no_access_penalty"] == 43200
    assert options["ignore_restrictions"] is False
    assert options["ignore_access"] is False


@pytest.mark.parametrize("field,value", [
    ("height", float("nan")), ("width", True), ("weight", -1), ("length", 999),
    ("axle_count", 2.5), ("axle_count", 0), ("axle_load", 1), ("hazmat", "false"),
])
def test_invalid_truck_profiles_rejected(field, value):
    with pytest.raises(ValueError):
        routing.route_payload(ORIGIN, DESTINATION, {**VEHICLE, field: value})


def test_response_keeps_geometry_vehicle_and_provenance():
    feature = routing.parse_truck_response(
        json.dumps(response()).encode(), ORIGIN, DESTINATION, VEHICLE
    )["features"][0]
    assert feature["geometry"]["coordinates"] == [ORIGIN, DESTINATION]
    assert feature["properties"]["vehicle"] == VEHICLE
    assert feature["properties"]["duration_minutes"] == 100
    assert feature["properties"]["profile"] == "truck"
    assert len(feature["properties"]["request_sha256"]) == 64


@pytest.mark.parametrize("defect", ["warning", "units", "summary", "snap", "shape", "no_route"])
def test_unusable_engine_results_fail_closed(defect):
    body = response()
    trip = body["trip"]
    if defect == "warning":
        trip["warnings"] = [{"description": "Value clamped"}]
    elif defect == "units":
        trip["units"] = "miles"
    elif defect == "summary":
        trip["legs"][0]["summary"]["length"] = 50
    elif defect == "snap":
        trip["legs"][0]["shape"] = encoded([[0, 0], [1, 1]])
    elif defect == "shape":
        trip["legs"][0]["shape"] = "_"
    else:
        body = {"error": "No route"}
    with pytest.raises(ValueError):
        routing.parse_truck_response(json.dumps(body).encode(), ORIGIN, DESTINATION, VEHICLE)


def test_no_network_until_operator_enables_demo(monkeypatch):
    monkeypatch.delenv("LOGINEXUS_TRUCK_DEMO_ENABLED", raising=False)
    with pytest.raises(ValueError, match="not enabled"):
        routing.request_truck_route(ORIGIN, DESTINATION, VEHICLE)


def test_provider_failure_is_not_retried_or_replaced(monkeypatch):
    attempts = []

    class Unavailable:
        def open(self, request, timeout):
            attempts.append((request, timeout))
            raise OSError("provider unavailable")

    monkeypatch.setenv("LOGINEXUS_TRUCK_DEMO_ENABLED", "true")
    monkeypatch.setattr(routing, "_last_request", float("-inf"))
    monkeypatch.setattr(routing, "_count", 0)
    monkeypatch.setattr(routing.urllib.request, "build_opener", lambda *args: Unavailable())
    with pytest.raises(ValueError, match="no car-route substitution"):
        routing.request_truck_route(ORIGIN, DESTINATION, VEHICLE)
    assert len(attempts) == 1
    assert attempts[0][1] == 20
    assert json.loads(attempts[0][0].data)["costing"] == "truck"
    with pytest.raises(ValueError, match="limit"):
        routing.request_truck_route(ORIGIN, DESTINATION, VEHICLE)
    assert len(attempts) == 1
