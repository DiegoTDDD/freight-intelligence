# Real-road geographic routes

In **Real road routes**, enter origin/destination latitude and longitude and confirm
coordinate sharing. The calculation requests OSRM routing over real OpenStreetMap
roads and displays a route line, distance, estimated duration and GeoJSON download.

The saved São Paulo–Campinas example was requested on 2026-11-12: approximately
93.17 km, 75.7 estimated minutes and 1,225 geometry points. Loading it makes no new
routing request. It is a historical response, not confirmation of current conditions.

## Profile and limitations

The public service uses a **reference car profile**. It does not certify truck access:
height, weight, axles, hazardous cargo, local permissions and tolls are not validated.
Duration excludes live traffic. The supplied-network workspace remains separate and
uses the restrictions explicitly provided with that network.

There is no inferred address, user tracking or automatic geolocation. Initial values
are public points in São Paulo and Campinas. New coordinates are sent only on explicit
submission with confirmation. The routing provider may log them; the basemap also
loads resources from an external provider. Do not submit private locations.

## Service and attribution

- [OSRM API documentation](https://project-osrm.org/docs/v5.24.0/api/).
- [Demo server policy](https://github.com/Project-OSRM/osrm-backend/wiki/Demo-server).
- [FOSSGIS usage and privacy](https://routing.openstreetmap.de/about.html).
- Data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL.

The demo is for light noncommercial use, with no uptime guarantee. The HTTPS client
identifies the application, enforces at least two seconds between requests per process
and uses a bounded 24-hour cache. There is no periodic polling or fabricated fallback.

Responses are limited to 2 MiB and 50,000 points. Invalid coordinates, road snaps above
1 km, redirects and missing routes are rejected. GeoJSON exports include the profile,
coordinates, snapped points, source, retrieval time, provider data version if supplied
and response hash. Attribution and a map-correction link appear in the interface.
Commercial or heavier use requires appropriate infrastructure and service terms;
this project does not automatically purchase those resources.
