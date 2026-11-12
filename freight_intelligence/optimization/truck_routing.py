"""Bounded Valhalla truck routing; map restrictions are not a dispatch certification."""

import hashlib
import json
import math
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

from freight_intelligence.optimization.geographic_routing import MAX_BYTES, NoRedirect, coordinates

ENDPOINT = "https://valhalla1.openstreetmap.de/route"
LIMITATIONS = (
    "Truck costing checks restrictions recorded in OpenStreetMap; missing or outdated map "
    "restrictions cannot be detected. No live traffic, legal clearance, toll pricing, "
    "driver-hours compliance or guaranteed availability. Demonstration planning only; "
    "independently verify the itinerary before dispatch."
)
PROFILES = {
    "Urban rigid truck (example)": {
        "height": 3.5, "width": 2.5, "length": 9.0, "weight": 16.0,
        "axle_load": 8.0, "axle_count": 2, "hazmat": False,
    },
    "Articulated truck (example)": {
        "height": 4.2, "width": 2.6, "length": 18.6, "weight": 40.0,
        "axle_load": 10.0, "axle_count": 5, "hazmat": False,
    },
}
_lock = threading.Lock()
_last_request = float("-inf")
_day = ""
_count = 0


def validate_vehicle(vehicle):
    required = {"height", "width", "length", "weight", "axle_load", "axle_count", "hazmat"}
    if not isinstance(vehicle, dict) or set(vehicle) != required:
        raise ValueError("A complete truck profile is required")
    for field, maximum in (("height", 10), ("width", 10), ("length", 50),
                           ("weight", 100), ("axle_load", 40)):
        value = vehicle[field]
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError(f"Invalid truck {field}")
    if type(vehicle["axle_count"]) is not int or not 2 <= vehicle["axle_count"] <= 12:
        raise ValueError("Truck axle count must be between 2 and 12")
    if type(vehicle["hazmat"]) is not bool:
        raise ValueError("Hazardous-material flag must be boolean")
    if not vehicle["weight"] / vehicle["axle_count"] <= vehicle["axle_load"] <= vehicle["weight"]:
        raise ValueError("Maximum axle load must cover average axle load and not exceed gross weight")
    return dict(vehicle)


def route_payload(origin, destination, vehicle):
    origin, destination = coordinates(*origin), coordinates(*destination)
    if origin == destination:
        raise ValueError("Choose different origin and destination points")
    options = validate_vehicle(vehicle)
    options.update(hgv_no_access_penalty=43200, ignore_restrictions=False,
                   ignore_access=False, ignore_oneways=False, ignore_closures=False)
    return {
        "locations": [{"lon": point[0], "lat": point[1], "type": "break",
                       "radius": 1000, "search_cutoff": 1000}
                      for point in (origin, destination)],
        "costing": "truck", "costing_options": {"truck": options},
        "units": "kilometers", "language": "en-US", "directions_type": "instructions",
    }


def decode_shape(shape):
    if not isinstance(shape, str) or not shape or len(shape) > MAX_BYTES:
        raise ValueError("Invalid truck route shape")
    position, latitude, longitude, path = 0, 0, 0, []
    while position < len(shape):
        deltas = []
        for _ in range(2):
            result, shift = 0, 0
            while True:
                if position >= len(shape) or shift > 30:
                    raise ValueError("Malformed truck route shape")
                byte = ord(shape[position]) - 63
                position += 1
                if not 0 <= byte <= 63:
                    raise ValueError("Malformed truck route shape")
                result |= (byte & 31) << shift
                shift += 5
                if byte < 32:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        latitude += deltas[0]
        longitude += deltas[1]
        path.append(coordinates(longitude / 1e6, latitude / 1e6))
        if len(path) > 50000:
            raise ValueError("Truck route has too many points")
    if len(path) < 2:
        raise ValueError("Truck route geometry is incomplete")
    return path


def distance_m(left, right):
    lon1, lat1, lon2, lat2 = map(math.radians, [*left, *right])
    term = math.sin((lat2 - lat1) / 2) ** 2 + (
        math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 12742000 * math.asin(min(1, math.sqrt(term)))


def parse_truck_response(payload, origin, destination, vehicle):
    validate_vehicle(vehicle)
    origin, destination = coordinates(*origin), coordinates(*destination)
    if not payload or len(payload) > MAX_BYTES:
        raise ValueError("Empty or oversized truck route response")
    try:
        body = json.loads(payload)
        trip = body["trip"]
        if trip["status"] != 0 or trip["units"] != "kilometers":
            raise ValueError("Truck engine did not return a valid kilometre itinerary")
        # Clamped/ignored inputs invalidate the promise to use the submitted profile.
        if body.get("warnings") or trip.get("warnings"):
            raise ValueError("Truck engine reported warnings; profile was not accepted unchanged")
        legs = trip["legs"]
        if len(legs) != 1:
            raise ValueError("Expected one truck route leg")
        path = decode_shape(legs[0]["shape"])
        snapped = [distance_m(origin, path[0]), distance_m(destination, path[-1])]
        if max(snapped) > 1000:
            raise ValueError("Truck route endpoints are more than 1 km from requested points")
        summary = trip["summary"]
        for field in ("length", "time"):
            value = summary[field]
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError("Invalid truck route summary")
            if not math.isclose(value, legs[0]["summary"][field], rel_tol=0.001, abs_tol=0.01):
                raise ValueError("Inconsistent truck route totals")
        maneuvers = legs[0]["maneuvers"]
        if not isinstance(maneuvers, list) or not 1 <= len(maneuvers) <= 5000:
            raise ValueError("Truck itinerary instructions are missing")
        instructions = []
        for item in maneuvers:
            instruction = item["instruction"]
            if not isinstance(instruction, str) or not 1 <= len(instruction) <= 2000:
                raise ValueError("Invalid truck itinerary instruction")
            instructions.append(instruction)
    except (KeyError, TypeError, IndexError, json.JSONDecodeError) as error:
        raise ValueError("Malformed truck route response") from error
    return {"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": {"type": "LineString", "coordinates": path},
        "properties": {
            "profile": "truck", "vehicle": dict(vehicle), "origin": origin,
            "destination": destination, "distance_km": summary["length"],
            "duration_minutes": summary["time"] / 60, "snap_distance_m": snapped,
            "instructions": instructions, "provider": "Valhalla / FOSSGIS demo",
            "source": "OpenStreetMap contributors", "endpoint": ENDPOINT,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "response_sha256": hashlib.sha256(payload).hexdigest(),
            "request_sha256": hashlib.sha256(json.dumps(
                route_payload(origin, destination, vehicle), sort_keys=True
            ).encode()).hexdigest(), "limitations": LIMITATIONS,
        },
    }]}


def request_truck_route(origin, destination, vehicle):
    payload = route_payload(origin, destination, vehicle)
    if os.environ.get("LOGINEXUS_TRUCK_DEMO_ENABLED") != "true":
        raise ValueError("Live truck routing is not enabled by the hosting operator")
    global _last_request, _day, _count
    with _lock:
        day = datetime.now(UTC).date().isoformat()
        if day != _day:
            _day, _count = day, 0
        now = time.monotonic()
        if now - _last_request < 2 or _count >= 100:
            raise ValueError("Truck routing request limit reached; use a saved route or try later")
        _last_request, _count = now, _count + 1
    request = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(), headers={
        "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "LogiNexus/0.1 (https://github.com/DiegoTDDD/freight-intelligence)",
        "X-Client-Id": "loginexus-dashboard-preview.onrender.com",
    })
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            raw = response.read(MAX_BYTES + 1)
    except (OSError, urllib.error.URLError) as error:
        raise ValueError("Truck routing unavailable; no car-route substitution was made") from error
    return parse_truck_response(raw, origin, destination, vehicle)
