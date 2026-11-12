"""Reference driving routes on real OSM roads through the bounded OSRM demo API."""

import hashlib
import json
import math
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

ENDPOINT = "https://router.project-osrm.org/route/v1/driving/"
MAX_BYTES = 2 * 1024 * 1024
_lock = threading.Lock()
_last_request = float("-inf")
LIMITATIONS = (
    "Trajeto de referência para automóvel sobre vias OpenStreetMap. Não valida altura, "
    "peso, eixos, carga perigosa, pedágios ou permissões de caminhões. Duração sem "
    "trânsito ao vivo. Confirme condições e restrições antes de qualquer viagem."
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def coordinates(longitude, latitude):
    if any(
        type(value) not in (int, float) or not math.isfinite(value)
        for value in (longitude, latitude)
    ):
        raise ValueError("Coordenadas precisam ser números finitos")
    if not -180 <= longitude <= 180 or not -85 <= latitude <= 85:
        raise ValueError("Longitude entre -180 e 180; latitude entre -85 e 85")
    return [float(longitude), float(latitude)]


def parse_response(payload, origin, destination):
    if not payload or len(payload) > MAX_BYTES:
        raise ValueError("Resposta de rota vazia ou acima do limite")
    body = json.loads(payload)
    if not isinstance(body, dict) or body.get("code") != "Ok" or not body.get("routes"):
        raise ValueError("O serviço não encontrou uma rota entre esses pontos")
    route = body["routes"][0]
    geometry = route.get("geometry", {})
    path = geometry.get("coordinates")
    if (
        geometry.get("type") != "LineString"
        or not isinstance(path, list)
        or not 2 <= len(path) <= 50000
    ):
        raise ValueError("Geometria de rota inválida")
    for point in path:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Ponto de rota inválido")
        coordinates(*point)
    for field in ("distance", "duration"):
        value = route.get(field)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Distância ou duração inválida")
    waypoints = body.get("waypoints", [])
    if len(waypoints) != 2:
        raise ValueError("Pontos ajustados à rede ausentes")
    for waypoint in waypoints:
        distance = waypoint.get("distance")
        if (
            type(distance) not in (int, float)
            or not math.isfinite(distance)
            or not 0 <= distance <= 1000
        ):
            raise ValueError("Coordenada distante demais de uma via roteável (máximo 1 km)")
        coordinates(*waypoint["location"])
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "distance_km": route["distance"] / 1000,
                    "duration_minutes": route["duration"] / 60,
                    "profile": "driving (car reference; not truck routing)",
                    "origin": origin,
                    "destination": destination,
                    "snapped_points": [point["location"] for point in waypoints],
                    "snap_distance_m": [point["distance"] for point in waypoints],
                    "provider": "OSRM demo / FOSSGIS",
                    "source": "OpenStreetMap contributors",
                    "attribution_url": "https://www.openstreetmap.org/copyright",
                    "retrieved_at": datetime.now(UTC).isoformat(),
                    "data_version": body.get("data_version", "not supplied by provider"),
                    "response_sha256": hashlib.sha256(payload).hexdigest(),
                    "limitations": LIMITATIONS,
                },
            }
        ],
    }


def request_route(origin_lon, origin_lat, destination_lon, destination_lat):
    origin = coordinates(origin_lon, origin_lat)
    destination = coordinates(destination_lon, destination_lat)
    if origin == destination:
        raise ValueError("Escolha origem e destino diferentes")
    global _last_request
    with _lock:
        now = time.monotonic()
        if now - _last_request < 2:
            raise ValueError("Aguarde dois segundos antes de consultar outra rota")
        _last_request = now
    points = ";".join(
        ",".join(f"{value:.6f}" for value in point) for point in (origin, destination)
    )
    url = (
        ENDPOINT
        + points
        + "?overview=full&geometries=geojson&steps=false&radiuses=1000;1000&generate_hints=false"
    )
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "LogiNexus/0.1 (https://github.com/DiegoTDDD/freight-intelligence)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            payload = response.read(MAX_BYTES + 1)
    except (OSError, urllib.error.URLError) as error:
        raise ValueError(
            "Serviço de rotas indisponível; tente mais tarde ou use uma rota salva"
        ) from error
    return parse_response(payload, origin, destination)
