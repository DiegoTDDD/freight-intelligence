import json

import pytest

from freight_intelligence.optimization import geographic_routing as routes


def response():
    return {
        "code": "Ok",
        "routes": [
            {
                "distance": 10000,
                "duration": 600,
                "geometry": {"type": "LineString", "coordinates": [[-46, -23], [-47, -22]]},
            }
        ],
        "waypoints": [
            {"distance": 1, "location": [-46, -23]},
            {"distance": 2, "location": [-47, -22]},
        ],
    }


def test_real_route_response_preserves_geometry_units_and_limits():
    result = routes.parse_response(json.dumps(response()).encode(), [-46, -23], [-47, -22])
    props = result["features"][0]["properties"]
    assert props["distance_km"] == 10
    assert props["duration_minutes"] == 10
    assert "not truck" in props["profile"]
    assert props["snap_distance_m"] == [1, 2]
    assert props["response_sha256"]


@pytest.mark.parametrize("point", [(181, 0), (0, 90), (True, 0), (0, float("nan"))])
def test_invalid_coordinates_never_contact_provider(point, monkeypatch):
    monkeypatch.setattr(routes.urllib.request, "build_opener", lambda *a: pytest.fail("network"))
    with pytest.raises(ValueError):
        routes.request_route(*point, -47, -22)


def test_missing_route_and_large_snap_are_rejected():
    with pytest.raises(ValueError, match="não encontrou"):
        routes.parse_response(b'{"code":"NoRoute"}', [0, 0], [1, 1])
    data = response()
    data["waypoints"][0]["distance"] = 2000
    with pytest.raises(ValueError, match="distante"):
        routes.parse_response(json.dumps(data).encode(), [0, 0], [1, 1])


def test_failed_provider_does_not_create_synthetic_route(monkeypatch):
    class Broken:
        def open(self, *args, **kwargs):
            raise OSError("unavailable")

    monkeypatch.setattr(routes, "_last_request", float("-inf"))
    monkeypatch.setattr(routes.urllib.request, "build_opener", lambda *a: Broken())
    with pytest.raises(ValueError, match="indisponível"):
        routes.request_route(-46, -23, -47, -22)
    with pytest.raises(ValueError, match="Aguarde"):
        routes.request_route(-46, -23, -47, -22)
